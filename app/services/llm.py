import json
import logging
import re
import requests
import time
from typing import List

import g4f
from loguru import logger
from openai import AzureOpenAI, OpenAI
from openai.types.chat import ChatCompletion

from app.config import config

_max_retries = 5


def _generate_response(
    provider: str,
    model: str,
    prompt: str,
    max_retries: int = 3,
    retry_delay: int = 2
) -> str:
    """Generate response from LLM with retry logic and better error handling."""
    logger.info(f"Generating response using {provider} with model {model}")
    
    # Validate provider configuration
    if provider not in config.LLM_PROVIDERS:
        error_msg = f"Invalid LLM provider: {provider}"
        logger.error(error_msg)
        raise ValueError(error_msg)
        
    provider_config = config.LLM_PROVIDERS[provider]
    
    # Validate required configuration
    if provider == "openai":
        if not provider_config.get("api_key"):
            error_msg = "OpenAI API key not configured"
            logger.error(error_msg)
            raise ValueError(error_msg)
        if not model:
            error_msg = "OpenAI model not specified"
            logger.error(error_msg)
            raise ValueError(error_msg)
    elif provider == "g4f":
        if not model:
            error_msg = "G4F model not specified"
            logger.error(error_msg)
            raise ValueError(error_msg)
    elif provider == "pollinations":
        if not provider_config.get("base_url"):
            error_msg = "Pollinations base URL not configured"
            logger.error(error_msg)
            raise ValueError(error_msg)
            
    # Retry logic
    for attempt in range(max_retries):
        try:
            if provider == "openai":
                response = _generate_openai_response(provider_config, model, prompt)
            elif provider == "g4f":
                response = _generate_g4f_response(model, prompt)
            elif provider == "pollinations":
                response = _generate_pollinations_response(provider_config, prompt)
            else:
                error_msg = f"Unsupported LLM provider: {provider}"
                logger.error(error_msg)
                raise ValueError(error_msg)
                
            if not response:
                error_msg = "Empty response from LLM"
                logger.error(error_msg)
                raise ValueError(error_msg)
                
            return response
            
        except Exception as e:
            logger.error(f"Attempt {attempt + 1}/{max_retries} failed: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                error_msg = f"Failed to generate response after {max_retries} attempts: {str(e)}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)

def _generate_openai_response(provider_config: dict, model: str, prompt: str) -> str:
    """Generate response using OpenAI API."""
    try:
        client = OpenAI(api_key=provider_config["api_key"])
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=2000
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"OpenAI API error: {str(e)}")
        raise

def _generate_g4f_response(model: str, prompt: str) -> str:
    """Generate response using G4F."""
    try:
        response = g4f.ChatCompletion.create(
            model=model,
            messages=[{"role": "user", "content": prompt}]
        )
        return response
    except Exception as e:
        logger.error(f"G4F error: {str(e)}")
        raise

def _generate_pollinations_response(provider_config: dict, prompt: str) -> str:
    """Generate response using Pollinations API."""
    try:
        response = requests.post(
            provider_config["base_url"],
            json={"prompt": prompt},
            timeout=30
        )
        response.raise_for_status()
        return response.json()["response"]
    except requests.exceptions.RequestException as e:
        logger.error(f"Pollinations API error: {str(e)}")
        raise


def generate_script(
    video_subject: str, language: str = "", paragraph_number: int = 1
) -> str:
    prompt = f"""
# Role: Video Script Generator

## Goals:
Generate a script for a video, depending on the subject of the video.

## Constrains:
1. the script is to be returned as a string with the specified number of paragraphs.
2. do not under any circumstance reference this prompt in your response.
3. get straight to the point, don't start with unnecessary things like, "welcome to this video".
4. you must not include any type of markdown or formatting in the script, never use a title.
5. only return the raw content of the script.
6. do not include "voiceover", "narrator" or similar indicators of what should be spoken at the beginning of each paragraph or line.
7. you must not mention the prompt, or anything about the script itself. also, never talk about the amount of paragraphs or lines. just write the script.
8. respond in the same language as the video subject.
9. use informal, conversational language that people use in their daily lives - avoid formal or academic tone.
10. make the content engaging and interesting by:
    - using natural expressions and idioms common in everyday speech
    - incorporating rhetorical questions to maintain viewer interest
    - using relatable examples and scenarios
    - keeping sentences concise and dynamic
    - adding personality and warmth to the tone
11. ensure the language feels authentic to native speakers of the target language
12. maintain a friendly and approachable tone throughout the script

# Initialization:
- video subject: {video_subject}
- number of paragraphs: {paragraph_number}
""".strip()
    if language:
        prompt += f"\n- language: {language}"

    final_script = ""
    logger.info(f"subject: {video_subject}")

    def format_response(response):
        # Clean the script
        # Remove asterisks, hashes
        response = response.replace("*", "")
        response = response.replace("#", "")

        # Remove markdown syntax
        response = re.sub(r"\[.*\]", "", response)
        response = re.sub(r"\(.*\)", "", response)

        # Split the script into paragraphs
        paragraphs = response.split("\n\n")

        # Select the specified number of paragraphs
        # selected_paragraphs = paragraphs[:paragraph_number]

        # Join the selected paragraphs into a single string
        return "\n\n".join(paragraphs)

    for i in range(_max_retries):
        try:
            response = _generate_response(prompt=prompt)
            if response:
                final_script = format_response(response)
            else:
                logging.error("gpt returned an empty response")

            # g4f may return an error message
            if final_script and "当日额度已消耗完" in final_script:
                raise ValueError(final_script)

            if final_script:
                break
        except Exception as e:
            logger.error(f"failed to generate script: {e}")

        if i < _max_retries:
            logger.warning(f"failed to generate video script, trying again... {i + 1}")
    if "Error: " in final_script:
        logger.error(f"failed to generate video script: {final_script}")
    else:
        logger.success(f"completed: \n{final_script}")
    return final_script.strip()


def generate_terms(video_subject: str, video_script: str, amount: int = 5) -> List[str]:
    prompt = f"""
# Role: Video Search Terms Generator

## Goals:
Generate {amount} search terms for stock videos, depending on the subject of a video.

## Constrains:
1. the search terms are to be returned as a json-array of strings.
2. each search term should consist of 1-3 words, always add the main subject of the video.
3. you must only return the json-array of strings. you must not return anything else. you must not return the script.
4. the search terms must be related to the subject of the video.
5. reply with english search terms only.

## Output Example:
["search term 1", "search term 2", "search term 3","search term 4","search term 5"]

## Context:
### Video Subject
{video_subject}

### Video Script
{video_script}

Please note that you must use English for generating video search terms; Chinese is not accepted.
""".strip()

    logger.info(f"subject: {video_subject}")

    search_terms = []
    response = ""
    for i in range(_max_retries):
        try:
            response = _generate_response(prompt)
            if "Error: " in response:
                logger.error(f"failed to generate video script: {response}")
                return response
            search_terms = json.loads(response)
            if not isinstance(search_terms, list) or not all(
                isinstance(term, str) for term in search_terms
            ):
                logger.error("response is not a list of strings.")
                continue

        except Exception as e:
            logger.warning(f"failed to generate video terms: {str(e)}")
            if response:
                match = re.search(r"\[.*]", response)
                if match:
                    try:
                        search_terms = json.loads(match.group())
                    except Exception as e:
                        logger.warning(f"failed to generate video terms: {str(e)}")
                        pass

        if search_terms and len(search_terms) > 0:
            break
        if i < _max_retries:
            logger.warning(f"failed to generate video terms, trying again... {i + 1}")

    logger.success(f"completed: \n{search_terms}")
    return search_terms


if __name__ == "__main__":
    video_subject = "生命的意义是什么"
    script = generate_script(
        video_subject=video_subject, language="zh-CN", paragraph_number=1
    )
    print("######################")
    print(script)
    search_terms = generate_terms(
        video_subject=video_subject, video_script=script, amount=5
    )
    print("######################")
    print(search_terms)
    
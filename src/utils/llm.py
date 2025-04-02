"""Helper functions for LLM"""

import json
from typing import TypeVar, Type, Optional, Any
from pydantic import BaseModel
from utils.progress import progress

T = TypeVar('T', bound=BaseModel)

def call_llm(
    prompt: Any,
    model_name: str,
    model_provider: str,
    pydantic_model: Type[T],
    agent_name: Optional[str] = None,
    max_retries: int = 3,
    default_factory = None
) -> T:
    """
    Makes an LLM call with retry logic, handling both Deepseek and non-Deepseek models.
    
    Args:
        prompt: The prompt to send to the LLM
        model_name: Name of the model to use
        model_provider: Provider of the model
        pydantic_model: The Pydantic model class to structure the output
        agent_name: Optional name of the agent for progress updates
        max_retries: Maximum number of retries (default: 3)
        default_factory: Optional factory function to create default response on failure
        
    Returns:
        An instance of the specified Pydantic model
    """
    from llm.models import get_model, get_model_info
    
    model_info = get_model_info(model_name)
    llm = get_model(model_name, model_provider)

    # --- Bypassing with_structured_output ---
    # # For non-JSON support models, we can use structured output
    # if not (model_info and not model_info.has_json_mode()):
    #     llm = llm.with_structured_output(
    #         pydantic_model,
    #         method="json_mode",
    #     )
    # --- End Bypass ---

    # Call the LLM with retries
    for attempt in range(max_retries):
        try:
            # Call the LLM - always get raw response
            result = llm.invoke(prompt)
            raw_content = result.content if hasattr(result, 'content') else str(result)

            # --- Manual Parsing Logic ---
            parsed_result = None
            try:
                # Attempt direct JSON parsing first
                parsed_result = json.loads(raw_content)
            except json.JSONDecodeError:
                # Fallback to markdown extraction if direct parsing fails
                parsed_result = extract_json_from_deepseek_response(raw_content)

            if parsed_result:
                try:
                    # Validate and instantiate the Pydantic model
                    return pydantic_model(**parsed_result)
                except Exception as validation_error:
                    print(f"Pydantic validation error: {validation_error}")
                    # Fall through to retry/default logic if validation fails
            # --- End Manual Parsing Logic ---

            # If parsing/validation failed, raise an error to trigger retry
            raise ValueError("Failed to parse or validate LLM response")

        except Exception as e:
            if agent_name:
                progress.update_status(agent_name, None, f"Error - retry {attempt + 1}/{max_retries}: {e}")
            
            if attempt == max_retries - 1:
                print(f"Error in LLM call after {max_retries} attempts: {e}")
                # Use default_factory if provided, otherwise create a basic default
                if default_factory:
                    return default_factory()
                return create_default_response(pydantic_model)

    # This should never be reached due to the retry logic above
    return create_default_response(pydantic_model)

def create_default_response(model_class: Type[T]) -> T:
    """Creates a safe default response based on the model's fields."""
    default_values = {}
    for field_name, field in model_class.model_fields.items():
        if field.annotation == str:
            default_values[field_name] = "Error in analysis, using default"
        elif field.annotation == float:
            default_values[field_name] = 0.0
        elif field.annotation == int:
            default_values[field_name] = 0
        elif hasattr(field.annotation, "__origin__") and field.annotation.__origin__ == dict:
            default_values[field_name] = {}
        else:
            # For other types (like Literal), try to use the first allowed value
            if hasattr(field.annotation, "__args__"):
                default_values[field_name] = field.annotation.__args__[0]
            else:
                default_values[field_name] = None
    
    return model_class(**default_values)

def extract_json_from_deepseek_response(content: str) -> Optional[dict]:
    """Extracts JSON from Deepseek's markdown-formatted response."""
    try:
        json_start = content.find("```json")
        if json_start != -1:
            json_text = content[json_start + 7:]  # Skip past ```json
            json_end = json_text.find("```")
            if json_end != -1:
                json_text = json_text[:json_end].strip()
                return json.loads(json_text)
    except Exception as e:
        print(f"Error extracting JSON from Deepseek response: {e}")
    return None

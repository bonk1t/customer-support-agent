from agents import ModelSettings
from agency_swarm import Agent
from agency_swarm.tools import ToolFactory
from openai.types.shared import Reasoning
import os
from dotenv import load_dotenv

load_dotenv()

# Import onboarding configuration
try:
    from onboarding_config import config
except ImportError:
    raise ImportError(
        "Onboarding configuration not found. Please run 'python onboarding_tool.py' "
        "to generate the configuration file before using this agent."
    )

current_dir = os.path.dirname(os.path.abspath(__file__))

def render_instructions():
    """Render instructions with config values"""
    # Determine which instructions file to use based on whether OpenAPI schema is provided
    if config.get("openapi_schema"):
        instructions_path = os.path.join(current_dir, "instructions_openapi.md")
    else:
        instructions_path = os.path.join(current_dir, "instructions.md")
    
    with open(instructions_path, "r") as file:
        instructions = file.read()
    
    # Format instructions with config values
    instructions = instructions.format(
        agent_name=config["agent_name"],
        company_name=config["company_name"],
        output_format=config["output_format"],
        support_contact=config.get("support_contact") or "the support team",
        additional_context=config.get("additional_context") or ""
    )
    
    return instructions

def load_openapi_tools():
    """Load OpenAPI schema from config and convert to tools with Bearer authentication"""
    tools = []
    
    # Get schema from config
    schema_content = config.get("openapi_schema")
    if not schema_content:
        return tools
    
    # Clean the schema content (strip whitespace)
    schema_content = schema_content.strip()
    
    # Get API key from environment
    api_key = os.getenv("CUSTOMER_SUPPORT_BEARER_TOKEN")
    
    try:
        # Prepare headers with Bearer authentication if API key is available
        headers = None
        if api_key:
            headers = {'Authorization': f'Bearer {api_key}'}
        
        # Convert schema to tools using ToolFactory
        schema_tools = ToolFactory.from_openapi_schema(
            schema_content,
            headers=headers,
            strict=False
        )
        
        tools.extend(schema_tools)
        
    except Exception as e:
        print(f"Warning: Failed to load OpenAPI schema: {str(e)}")
    
    return tools

# Load OpenAPI tools
openapi_tools = load_openapi_tools()

# Build agent parameters based on model selection
agent_params = {
    "name": config["agent_name"],
    "description": config["agent_description"],
    "instructions": render_instructions(),
    "tools_folder": "./tools",
    "files_folder": "./files",
    "model": config.get("model", "gpt-5"),
    "tools": openapi_tools if openapi_tools else []
}

# Conditionally add input guardrail
if config.get("enable_guardrail", True):
    import sys
    import importlib.util
    
    # Load guardrail module
    guardrail_path = os.path.join(current_dir, "input_guardrail.py")
    spec = importlib.util.spec_from_file_location("input_guardrail", guardrail_path)
    guardrail_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guardrail_module)
    
    agent_params["input_guardrails"] = [guardrail_module.relevance_guardrail]
    agent_params["throw_input_guardrail_error"] = False

# Conditionally add model settings based on model type
selected_model = config.get("model", "gpt-5")
if selected_model == "gpt-5":
    # gpt-5 uses reasoning
    agent_params["model_settings"] = ModelSettings(
        reasoning=Reasoning(
            effort="low",
            summary="auto",
        ),
    )
else:
    # gpt-4.1 uses temperature instead of reasoning
    agent_params["model_settings"] = ModelSettings(
        temperature=0.3
    )

customer_support_agent = Agent(**agent_params)


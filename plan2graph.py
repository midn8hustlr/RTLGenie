from langchain.chat_models import init_chat_model
from typing import Optional
from pydantic import BaseModel, Field
import json
from utils import VerilogKnowledgeGraph
from prompts import *


def plan2graph(spec: str, plans: list[dict]) -> VerilogKnowledgeGraph:
    """
    Creates a knowledge graph from a Verilog design description and plans.
    
    Args:
        spec (str): The design description
        plans (list[dict]): Plans and descriptions in order
        
    Returns:
        nx.DiGraph: The generated knowledge graph
    """
    # Initialize LLM
    llm = init_chat_model("bedrock_converse:anthropic.claude-3-5-sonnet-20241022-v2:0")
    
    # Define entity models
    class Entity(BaseModel):
        """An named entity with a description."""
        name: str = Field(description="A unique name of the entity")
        description: str = Field(description="The description/example of the entity")

    class Entities(BaseModel):
        """A class which represents all the extracted entities from a design specification."""
        signals: Optional[list[Entity]] = Field(description="List of signal entities")
        fsm_states: Optional[list[Entity]] = Field(default=None, description="List of fsm_state entities")
        signal_examples: Optional[list[Entity]] = Field(default=None, description="List signal example entities")

    # Extract entities from description
    entities = llm.with_structured_output(Entities).invoke(ENTITY_EXTRACT_PROMPT.format(spec=spec))
    
    # Merge plans with extracted entities into a single structure
    full_json = {
        "plans": plans,
        "signals": entities.model_dump().get("signals", []),
        "fsm_states": entities.model_dump().get("fsm_states", []),
        "signal_examples": entities.model_dump().get("signal_examples", [])
    }
    full_json = json.dumps(full_json, indent=2)
    
    # Extract relationships
    class Plan(BaseModel):
        """Plan containing name, description and related signals."""
        name: str = Field(description="The name of the plan")
        signals: Optional[list[str]] = Field(default=None, description="The list signal names implemented/declared by the plan")

    class Signal(BaseModel):
        """Signal containing name, influencing fsm_states and related examples."""
        name: str = Field(description="The name of the signal")
        fsm_states: Optional[list[str]] = Field(default=None, description="The list of fsm_state names impacting the signal")
        examples: Optional[list[str]] = Field(default=None, description="The list signal_example names which provides examples of the signal")

    class Relationships(BaseModel):
        """A class which defines the relationships among entities."""
        plans: list[Plan] = Field(description="List of plans")
        signals: list[Signal] = Field(description="List of signals")

    relationships = llm.with_structured_output(Relationships).invoke(
        RELATIONSHIP_EXTRACT_PROMPT.format(json_struct=full_json)
    )
    relationships_json = relationships.model_dump_json(indent=2)
    
    # Create and build the knowledge graph
    graph = VerilogKnowledgeGraph(full_json, relationships_json)
    graph.build_graph()
    
    return graph

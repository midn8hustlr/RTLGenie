import json
from langchain.chat_models import init_chat_model
from prompts import *
from utils import VerilogKnowledgeGraph


def graph2tasks(spec: str, kg: VerilogKnowledgeGraph) -> list[str]:
    """Generate relationships between plans, signals, states, and examples."""
    from typing import List
    from pydantic import BaseModel, Field

    class PlanRelations(BaseModel):
        """Plan with related signals, states and examples."""
        plan: str = ""
        signals: List[str] = []
        fsm_states: List[str] = []
        examples: List[str] = []

    class PlansRelations(BaseModel):
        """Collection of all plans with their relationships."""
        plans: List[PlanRelations] = []
        
    class FinalPlans(BaseModel):
        """Final plans draft."""
        plans: List[str] = Field(description="List of the plans")

    def get_plan_relationships(knowledge_graph, plan_name: str, depth: int = 3) -> PlanRelations:
        """
        Build a PlanRelations object by traversing relationships in the knowledge graph.
        
        Args:
            knowledge_graph: The knowledge graph object with BFS capability
            plan_name: Name of the plan to find relationships for
            depth: How deep to search in the graph
        
        Returns:
            PlanRelations object with populated relationships
        """
        plan_relations = PlanRelations()
        related_nodes = knowledge_graph.bfs_relationship(plan_name, depth)
        
        # Process relationships from BFS traversal
        for level in related_nodes:
            for relationship in level:
                target_node = relationship['target']
                if not target_node or target_node not in knowledge_graph.G.nodes:
                    continue
                    
                node_type = knowledge_graph.G.nodes[target_node].get('type', 'unknown')
                node_desc = knowledge_graph.G.nodes[target_node].get('description', 'No description available')
                formatted_info = f"{target_node}: {node_desc}"
                
                # Add information to appropriate category
                if node_type == 'plan':
                    plan_relations.plan = formatted_info
                elif node_type == 'signal' and formatted_info not in plan_relations.signals:
                    plan_relations.signals.append(formatted_info)
                elif node_type == 'fsm_state' and formatted_info not in plan_relations.fsm_states:
                    plan_relations.fsm_states.append(formatted_info)
                elif node_type == 'example' and formatted_info not in plan_relations.examples:
                    plan_relations.examples.append(formatted_info)
        
        return plan_relations

    # Fetch all plan IDs from the knowledge graph
    plan_ids = [item['name'] for item in kg.query_graph("list_entities", entity_type="plan")]
    
    # Build the complete plans relations structure
    plans_relations = PlansRelations(
        plans=[get_plan_relationships(kg, plan_id) for plan_id in plan_ids]
    )
    
    # Generate JSON output
    json_output = plans_relations.model_dump_json(indent=2)
    
    # Process with LLM 
    llm = init_chat_model("bedrock_converse:anthropic.claude-3-5-sonnet-20241022-v2:0")
    final_plans = llm.with_structured_output(FinalPlans).invoke(
        PLAN_EXTRACT_PROMPT.format(spec=spec, json_struct=json_output)
    )
    
    return final_plans.plans
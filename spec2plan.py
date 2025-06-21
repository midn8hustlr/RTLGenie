from autogen import LLMConfig
from utils import extract_json_from_markdown, ChainlitAssistantAgent
from prompts import *


def spec2plan(spec: str, llm_config_path: str = "LLM_CONFIG") -> list[dict]:
  """
  Process a specification and generate a task list for RTL implementation.
  
  Args:
    spec: String containing the RTL specification
    llm_config_path: Path to LLM configuration file
  
  Returns:
    list[dict] containing the planned tasks
  """
  llm_config = LLMConfig.from_json(path=llm_config_path)
  llm_config.cache_seed = None


  planner = ChainlitAssistantAgent(
    name="planner",
    description="Planner assistant to break down the task into subtasks for completing the verilog code.",
    system_message=PLANNER_SYSTEM_MESSAGE,
    is_termination_msg=lambda x: x.get("content", "").find("TERMINATE") >= 0,
    human_input_mode="NEVER",
    llm_config=llm_config,
  )

  plan_reviewer = ChainlitAssistantAgent(
    name="plan_reviewer",
    description="Assistant who verify the subtasks and plan from planner match the user instruction.",
    system_message=PLAN_REVIEWER_SYSTEM_MESSAGE,
    is_termination_msg=lambda x: x.get("content", "").find("TERMINATE") >= 0,
    human_input_mode="NEVER",
    llm_config=llm_config,
  )

  plan_reviewer.initiate_chat(
    recipient=planner,
    message=PLANNER_PROMPT.format(spec=spec),
    max_turns=10,
    summary_method="last_msg"
  )

  task_list= extract_json_from_markdown(
    plan_reviewer.chat_messages_for_summary(planner)[-2]['content']
  )
  
  return task_list['tasks'] if task_list is not None else []

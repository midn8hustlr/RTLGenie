from collections import deque
import os
from typing import Any
from utils import VerilogToolKits, ChainlitAssistantAgent, ChainlitUserProxyAgent
from prompts import RTL_DESIGNER_SYSTEM_MESSAGE, RTL_REVIEWER_SYSTEM_MESSAGE, RTL_DESIGNER_PROMPT

from autogen import (
    AfterWork,
    AfterWorkOption,
    ConversableAgent,
    LLMConfig,
    OnCondition,
    SwarmResult,
    UserProxyAgent,
    initiate_swarm_chat,
    register_hand_off,
    GroupChat,
    Agent
)

from typing import Annotated
import chainlit as cl


def generate_rtl(spec: str, tasks: list[str], work_dir: str = "./work", llm_config_path: str = "LLM_CONFIG") -> tuple[str, str]:
    """
    Generate RTL code for the given specification and tasks.
    
    Args:
        spec: The specification for RTL generation
        tasks: List of tasks to implement in RTL
        llm_config_path: Path to the LLM configuration file
    
    Returns:
        The generated RTL code as a string
    """
    llm_config = LLMConfig.from_json(
        path=llm_config_path
    )

    os.makedirs(work_dir, exist_ok=True)
    vtk = VerilogToolKits(work_dir)

    def verilog_syntax_check_tool(
            completed_verilog: Annotated[str, "The completed verilog module code implementation"],
            context_variables: dict
        ) -> SwarmResult:
        """
        Use this tool to examine the syntax and correctness of completed verilog module.
        Input the completed verilog module in string format. Output is the string of pass or failed.
        """
        [compile_pass, log] = vtk.verilog_syntax_check_tool(completed_verilog=completed_verilog)
        cl.run_sync(
            cl.Message(
                content=f'***** Response from calling tool *****\n\n{log}',
                author="tool call",
            ).send()
        )

        if context_variables["interface"] in ("", None) and compile_pass:
            context_variables["interface"] = completed_verilog

        context_variables["compile_pass"] = compile_pass
        context_variables["code"] = completed_verilog if compile_pass else None
        next_agent = rtl_reviewer if compile_pass else rtl_designer

        return SwarmResult(
            context_variables=context_variables,
            values=log,
            agent=next_agent
        )

    user = ChainlitUserProxyAgent(
        name="user",
        human_input_mode="NEVER",
        code_execution_config=False
    )

    rtl_designer = ChainlitAssistantAgent(
        name="rtl_designer",
        description="Assistant who writes RTL code in verilog.",
        system_message=RTL_DESIGNER_SYSTEM_MESSAGE,
        functions=[verilog_syntax_check_tool],
        llm_config=llm_config,
    )

    rtl_reviewer = ChainlitAssistantAgent(
        name="rtl_reviewer",
        description="Assistant who reviews RTL code in verilog.",
        system_message=RTL_REVIEWER_SYSTEM_MESSAGE,
        llm_config=llm_config,
    )

    workflow_context = {
        "sim_pass": False,
        "rtl_generated": False,
        "compile_pass": False,
        "code": "",
        "interface": "",
        "task_current": dict(),
        "tasks_completed": deque(),
        "tasks_remaining": deque(tasks),
        "spec": spec,
        "dummy_true": True,
        "dummy_false": False
    }

    def custom_reply(recipient, messages, sender, config):
        tasks_remaining = sender.get_context("tasks_remaining")
        if tasks_remaining:
            task_current = tasks_remaining.popleft()
            recipient.set_context("task_current", task_current)
            recipient.set_context("tasks_remaining", tasks_remaining)
            recipient.set_context("compile_pass", False)
            prompt = RTL_DESIGNER_PROMPT.format(
                spec=sender.get_context("spec"),
                code=sender.get_context("code"),
                subtask=task_current
            )
            return True, prompt
        else:
            recipient.set_context("rtl_generated", True)
            return True, "All tasks are completed."

    user.register_reply(trigger=[Agent, None], reply_func=custom_reply)

    def user_after_work_func(last_speaker: ConversableAgent, messages: list[dict[str, Any]], groupchat: GroupChat):
        return AfterWorkOption.TERMINATE if last_speaker.get_context("rtl_generated") else rtl_designer

    register_hand_off(
        agent=user,
        hand_to=AfterWork(user_after_work_func)
    )

    register_hand_off(
        agent=rtl_designer,
        hand_to=[
            OnCondition(
                target=rtl_reviewer,
                condition="Subtask is implemented and compilation is passing."
            ),
            OnCondition(
                target=user,
                condition="RTL has been reviewed and you are ready to proceed to next task"
            ),
            AfterWork(user),
        ],
    )

    register_hand_off(
        agent=rtl_reviewer,
        hand_to=[
            OnCondition(
                target=user,
                condition="If the generated Verilog code implementation meets the subtask requirement correctly, then proceed to next subtask.",
            ),
            AfterWork(rtl_designer)
        ],
    )

    chat_history = initiate_swarm_chat(
        initial_agent=user,
        agents=[user, rtl_designer, rtl_reviewer],
        context_variables=workflow_context,
        messages="",
        max_rounds=200,
        after_work=AfterWorkOption.REVERT_TO_USER
    )
    
    # Return the generated code from the workflow context
    return workflow_context["code"], workflow_context["interface"]

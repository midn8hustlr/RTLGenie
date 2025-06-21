from collections import deque
import os
from typing import Any, List
from utils import VerilogToolKits, get_traces, ChainlitAssistantAgent, ChainlitUserProxyAgent
from prompts import TB_DESIGNER_SYSTEM_MESSAGE, TB_REVIEWER_SYSTEM_MESSAGE, TB_DESIGNER_EXAMPLES, TB_DESIGNER_PROMPT

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

def generate_tb(spec: str, interface: str, messages, work_dir: str = "./work", llm_config_path: str = "LLM_CONFIG"):

    llm_config = LLMConfig.from_json(
        path=llm_config_path
    )

    os.makedirs(work_dir, exist_ok=True)
    vtk = VerilogToolKits(work_dir)
    vtk.load_interface(interface)

    def tb_syntax_check_tool(
            completed_verilog: Annotated[str, "The completed verilog testbench code implementation"],
            context_variables: dict
        ) -> SwarmResult:
        """
        Use this tool to examine the syntax and correctness of completed verilog testbench.
        Input the completed verilog testbench module in string format. Output is the string of pass or failed.
        """
        [compile_pass, log] = vtk.tb_syntax_check_tool(completed_verilog=completed_verilog)
        cl.run_sync(
                cl.Message(
                    content=f'***** Response from calling tool *****\n\n{log}',
                    author="tool call",
                ).send()
            )

        context_variables["compile_pass"] = compile_pass
        context_variables["code"] = completed_verilog if compile_pass else None
        next_agent = tb_reviewer if compile_pass else tb_designer

        return SwarmResult(
            context_variables=context_variables,
            values=log,
            agent=next_agent
        )

    def waveform_trace_tool(
            signals: Annotated[List[str], "List of signals to trace in the waveform"],
            start_time: Annotated[int, "Time (units) from which to trace signals"] = 0,
            end_time: Annotated[int, "Time (units) till which to trace signals"] = 100
        ) -> Annotated[str, "Tabular waveform trace in text format"]:
        """
        Trace the functionally incorrect signal waveforms.
        """
        return get_traces(f"{work_dir}/wave.vcd", signals, start_time, (end_time-start_time), "tb.clk") + \
               "\n\n**Please use the `waveform_trace_tool` again with some more signals/time if you are not 100 % sure about the bug in tb. " + \
               "Suggest changes to the 'tb_designer' based on the 'user' feedback and waveform.**\n" 

    user = ChainlitUserProxyAgent(
        name="user",
        human_input_mode="NEVER",  # Disables prompting for user input
        code_execution_config=False
    )

    tb_designer = ChainlitAssistantAgent(
        name="tb_designer",
        description="Assistant who writes Testbench code in verilog.",
        system_message=TB_DESIGNER_SYSTEM_MESSAGE.format(TB_DESIGNER_EXAMPLES=TB_DESIGNER_EXAMPLES),
        functions=[tb_syntax_check_tool],
        llm_config=llm_config,
    )

    tb_reviewer = ChainlitAssistantAgent(
        name="tb_reviewer",
        description="Assistant who reviews Testbench code in verilog.",
        system_message=TB_REVIEWER_SYSTEM_MESSAGE,
        functions=[waveform_trace_tool],
        llm_config=llm_config,
    )

    #register_hand_off(
    #    agent=tb_reviewer,
    #    hand_to=[
    #        OnCondition(
    #            target=tb_designer,
    #            condition="The generated testbench doesn't meets the testbench requirement correctly.",
    #        ),
    #        OnCondition(
    #            target=tb_designer,
    #            condition="The user provided feedback is not fixed in the tb by the 'tb_designer'.",
    #        ),
    #        AfterWork(AfterWorkOption.TERMINATE)
    #    ]
    #)

    register_hand_off(
        agent=tb_reviewer,
        hand_to=[
            OnCondition(
                target=user,
                condition="The generated testbench meets the testbench requirement correctly.",
            ),
            AfterWork(tb_designer)
        ]
    )

    register_hand_off(
        agent=user,
        hand_to=[
            AfterWork(AfterWorkOption.TERMINATE)
        ]
    )

    workflow_context = {
        "tb_generated": False,
        "compile_pass": False,
        "code": "",
        "spec": spec,
        "interface": interface,
        "review": []
    }

    initial_agent = tb_designer if len(messages) < 2 else tb_reviewer

    chat_history = initiate_swarm_chat(
        initial_agent=initial_agent,
        agents=[tb_designer, tb_reviewer, user],
        context_variables=workflow_context,  # Our shared context
        messages=messages,
        max_rounds=40  # Maximum number of turns
    )

    # Return the generated code from the workflow context
    return workflow_context["code"], chat_history[0].chat_history


# IMPORTS
import os
from typing import Annotated, Any, List, LiteralString
from utils import VerilogToolKits, get_traces, ChainlitAssistantAgent, ChainlitUserProxyAgent
from prompts import RTL_DEBUGGER_SYSTEM_MESSAGE, RTL_DEBUGGER_PROMPT
from prompts import TB_DESIGNER_SYSTEM_MESSAGE, TB_REVIEWER_SYSTEM_MESSAGE, TB_DESIGNER_EXAMPLES, TB_DESIGNER_PROMPT
from generate_tb import generate_tb
import chainlit as cl

# AG2 imports
from autogen import (
    AfterWork,
    AfterWorkOption,
    ConversableAgent,
    LLMConfig,
    OnCondition,
    OnContextCondition,
    SwarmResult,
    UserProxyAgent,
    initiate_swarm_chat,
    register_hand_off,
    GroupChat,
    Agent
)

def verify_rtl(spec, code, interface, ref_rtl_path, testbench_code, use_dataset_tb, work_dir="./work", llm_config_path="LLM_CONFIG"):
    """
    Debug and fix RTL code using an AI agent workflow.
    
    Args:
        testbench_code (str): Testbench code for the RTL design
        ref_rtl_path (str): Path to the reference RTL implementation
        llm_config_path (str): Path to the LLM configuration file
        work_dir (str): Working directory for the verification tools
        
    Returns:
        str: The corrected RTL code if simulation passes, None otherwise
    """
    # Load configuration and files
    llm_config = LLMConfig.from_json(path=llm_config_path)
    
    # Initialize tools
    os.makedirs(work_dir, exist_ok=True)
    vtk = VerilogToolKits(work_dir)
    vtk.load_interface(interface)
    vtk.load_ref_rtl_path(ref_rtl_path)
    if use_dataset_tb:
        vtk.load_ref_rtl_path(ref_rtl_path)
        vtk.load_test_bench(testbench_code)

    def verilog_simulation_tool(
            completed_verilog: Annotated[str, "The completed verilog module code implementation"],
            context_variables: dict
        ) -> SwarmResult:
        """
        Examine the syntax and functional correctness of completed verilog module.
        """

        vtk.load_test_bench(context_variables["tb"])
        compile_pass, sim_pass, sim_log = vtk.verilog_simulation_tool(completed_verilog=completed_verilog)

        cl.run_sync(
                cl.Message(
                    content=f'***** Response from calling tool *****\n\nComplile_pass: {compile_pass}\nSim_pass: {sim_pass}\nSim_log: {sim_log}',
                    author="tool call",
                ).send()
            )

        context_variables["code"] = completed_verilog if compile_pass else None
        context_variables["compile_pass"] = compile_pass
        context_variables["sim_pass"] = sim_pass

        values = f"Simulation passed successfully.\n==Tool Output==\n{sim_log}" if sim_pass else sim_log
        if sim_pass:
            next_agent = AfterWorkOption.TERMINATE
        elif context_variables["use_dataset_tb"] or context_variables["tb_verified"]:
            next_agent = rtl_designer
        else:
            next_agent = user

        return SwarmResult(
            context_variables=context_variables,
            values=values,
            agent=next_agent,
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
               "\n\n**Please use the `waveform_trace_tool` again with some more signals/time if you are not 100 % sure about the bug. " + \
               "Don't fix the code if you don't have enough information from the waveform.**\n" 

    # Initialize workflow context and agents
    workflow_context = {
        "compile_pass": False,
        "sim_pass": False,
        "code": code, 
        "tb_verified": False,
        "tb": testbench_code if use_dataset_tb else "",
        "spec": spec,
        "nested_chat_history": [],
        "first_time": True,
        "use_dataset_tb": use_dataset_tb,
        "work_dir": work_dir
    }

    user = ChainlitUserProxyAgent(
        name="user",
        default_auto_reply="Please continue.",
        code_execution_config=False
    )

    rtl_designer = ChainlitAssistantAgent(
        name="rtl_designer",
        description="Assistant who writes RTL code in verilog.",
        system_message=RTL_DEBUGGER_SYSTEM_MESSAGE,
        functions=[verilog_simulation_tool, waveform_trace_tool],
        llm_config=llm_config,
    )

    def user_custom_reply(recipient, messages, sender, config):
        messages = sender.get_context("nested_chat_history")
        tb = sender.get_context("tb")
        code = sender.get_context("code")
        work_dir = sender.get_context("work_dir")

        if sender.get_context("use_dataset_tb"):
            return True, RTL_DEBUGGER_PROMPT.format(spec=spec, code=code, tb_code=tb)

        if not tb.strip():
            message = TB_DESIGNER_PROMPT.format(spec=spec, interface=interface)
        else:
            # message = input("Check the waveform/tb for bugs and give suggestions to fix the tb (or press ENTER if tb is correct):\n")
            message = cl.run_sync(cl.AskUserMessage(content="Check the waveform/tb for bugs and give suggestions to fix the tb (type `exit` if tb is correct):\n", timeout=100).send())
            # print(message)
            # if not message.strip():
            if not message or message.get("output").strip().lower() == "exit":
                recipient.set_context("tb_verified", True)
                return True, "Testbench is correct. Please proceed to fix the bug in RTL."
                
        messages.append({"content": message, "name": "user", "role": "user"})
        tb, tb_gen_history = generate_tb(spec, interface, messages, work_dir)

        recipient.set_context("nested_chat_history", tb_gen_history)

        if sender.get_context("first_time"):
            recipient.set_context("first_time", False)
            prompt = RTL_DEBUGGER_PROMPT.format(spec=spec, code=code, tb_code=tb)
        else:
            prompt = "Sorry, there was an issue with the testbench. I have fixed the tb. Please use the 'verilog_simulation_tool' again.\n\n" + tb

        recipient.set_context("tb", tb)

        return True, prompt

    user.register_reply(trigger=[Agent, None], reply_func=user_custom_reply)

    def user_after_work_func(last_speaker: ConversableAgent, messages: list[dict[str, Any]], groupchat: GroupChat):
        return rtl_designer

    register_hand_off(
        agent=user,
        hand_to=AfterWork(user_after_work_func)
    )

    chat_history = initiate_swarm_chat(
        initial_agent=user,
        agents=[user, rtl_designer],
        context_variables=workflow_context,
        messages="",
        #user_agent=user,  # Human-in-the-loop
        max_rounds=40,
        after_work=AfterWorkOption.TERMINATE
    )

    # Return the fixed code if available
    return workflow_context['sim_pass'], workflow_context["code"], workflow_context["tb"]

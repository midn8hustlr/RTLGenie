
# IMPORTS
import os
from typing import Annotated, Any, List, LiteralString
from utils import VerilogToolKits, get_traces
from prompts import RTL_DEBUGGER_SYSTEM_MESSAGE, RTL_DEBUGGER_PROMPT

# AG2 imports
from autogen import (
    AfterWorkOption,
    ConversableAgent,
    LLMConfig,
    SwarmResult,
    initiate_swarm_chat,
)

def verify_rtl(spec, code, testbench_code, ref_rtl_path, llm_config_path="LLM_CONFIG", work_dir="./work"):
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
    vtk.load_test_bench(testbench_code)
    vtk.load_ref_rtl_path(ref_rtl_path)

    def verilog_simulation_tool(
            completed_verilog: Annotated[str, "The completed verilog module code implementation"],
            context_variables: dict
        ) -> SwarmResult:
        """
        Examine the syntax and functional correctness of completed verilog module.
        """
        compile_pass, sim_pass, sim_log = vtk.verilog_simulation_tool(completed_verilog=completed_verilog)

        context_variables["code"] = completed_verilog if compile_pass else None
        context_variables["compile_pass"] = compile_pass
        context_variables["sim_pass"] = sim_pass

        values = "Simulation passed successfully." if sim_pass else sim_log
        next_agent = AfterWorkOption.TERMINATE if sim_pass else rtl_designer

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
        "code": None, 
    }

    rtl_designer = ConversableAgent(
        name="rtl_designer",
        description="Assistant who writes RTL code in verilog.",
        system_message=RTL_DEBUGGER_SYSTEM_MESSAGE,
        functions=[verilog_simulation_tool, waveform_trace_tool],
        llm_config=llm_config,
    )

    chat_history = initiate_swarm_chat(
        initial_agent=rtl_designer,
        agents=[rtl_designer],
        context_variables=workflow_context,
        messages=RTL_DEBUGGER_PROMPT.format(spec=spec, code=code, tb_code=testbench_code),
        max_rounds=40,
        after_work=AfterWorkOption.TERMINATE
    )

    # Return the fixed code if available
    return workflow_context['sim_pass'], workflow_context["code"]

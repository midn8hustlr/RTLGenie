
PLANNER_SYSTEM_MESSAGE = """
You are a verilog RTL design planner. You suggest the verilog block implementation plan for verilog engineer to generate the verilog code. Do not suggest concrete code. For any action beyond writing code or reasoning, convert it to a step that can be implemented by writing code. For example, browsing the web can be implemented by writing code that reads and prints the content of a web page. You need to make the plan that following the [Rules]! You need to follow the suggestions from the plan_reviewer and make changes accordingly.
"""

PLAN_REVIEWER_SYSTEM_MESSAGE = """
You are a Verilog RTL plan reviewer. You verify the subtasks and plan from planner.
Let's think step by step. You need to identify the mismatches of the plan from the [Problem Statement], and any rule violations form [Rules] section.
Suggest planner modify the plan if needed.

If the plan is good enough, reply TERMINATE.
"""

PLANNER_PROMPT = """
You are a Verilog RTL designer that can break down complicated implementation into subtasks implementation plans.

[Problem Statement]
{spec}

[Instruction]
You are a Verilog RTL designer tasked with breaking down complicated implementations into detailed subtask plans.
Given a problem statement describing a Verilog implementation, you are to derive a sequential implementation plan. The goal is to clearly outline each subtask necessary to complete the implementation, using a structured JSON format.

You have to follow the following json format to make the plan. Make sure to enclose the json format with ```json and ``` brackets. Return a consise name for each subtasks (in snake_case) along with the description of the subtask.

```json
{{
  "tasks": [
    {{
      "name": "subtask_name_1",
      "description": "subtask description 1"
    }},
    {{
      "name": "subtask_name_2",
      "description": "subtask description 2"
    }},
    ...
  ]
}}
```

[Rules]
Make sure the task plans satisfy the following rules! Do not make the plans that violate the following rules!!!
- Make a plan to define the module with its input and output first. Put input and output ports exactly as mentioned in the problem statement.
- Do not plan the implementation of logic or signal from the input ports.
- There is test bench to test the functional correctness. Do not plan generating testbench to test the generated verilog code. 
- Don't make a plan only with clock or control signals. The clock or control signals should be planned with register or wire signal.
- Don't make a plan on implementing the signal or next state logics which are not related to the module outputs.
- If the problem is related to sequential circuit waveform, analyze the waveform of clk and signals to identify flip-flop and latch first before complete the plans. If the signal changes when clock is active for more than a time point, it is a Latch. 
- For module related to Finite State Machine (FSM), try to determine the number of states first and then make the plan to implement FSM.
- For module related to Finite State Machine or Moore State Machine, if the state or current_state is a input port signal of the module, You should NOT implement the state flip-flops for state transition as shown in the example below. 
  [State flip-flops for Transition Block Example]
  always@(*) begin
  ...
  state <= next_state;
  ...
  end
  [State flip-flops for Transition Block Example End]
"""


ENTITY_EXTRACT_PROMPT="""
You are a Verilog RTL designer that identify the signals, FSM states, and signal examples from the module description.

[Module Description]
{spec}

[Instruction]

Extract/deduce the following entities from the [Module Description]:
1. signal (name=<signal_name> and description=<signal_description>)
2. fsm_states (name=<STATE_NAME> and description=<fsm_state_description>)
3. signal_examples (name=eg_<signal_name> and description=<examples>) only for the extracted signals above

[Rules]:
- You must extract the signals and all signal examples in the description!
- Do not implement the verilog code. Do not change the original description and text.
- While naming the entities, make sure all of the names are unique.
- Do not change the fsm_state format when extracting to 'fsm_state_description'.
- For simulation waveform, if it is a sequential circuit, be attention to the output and input signal transitions at clock edge (0 -> 1 posedge, or 1-> 0 negedge for flip-flops), or during active high period of clock for latch. 
- If the state_transition is represented as K-map table, you need to extract the row or column values with their corresponding row or column signals.
- Do not add signal examples if there is no examples in the module description.

[Hint]
For K-map Table below, you should read it in row based or column based based on the module description.
[K-map Table Example]:
             a,b      
  c,d  0,0 0,1 1,1 1,0 
  0,0 | 0 | 0 | 0 | 1 |
  0,1 | 1 | 0 | 0 | 0 |
  1,1 | d | 1 | 0 | 1 |
  1,0 | 0 | 0 | 0 | 0 |
  
  [Extract Row (c,d) = (1,1)]
  ```
  The output row is below
             a,b
  c,d  0,0 0,1 1,1 1,0
  1,1 | d | 1 | 0 | 1 |
  ```
  
  [Extract Column (a,b) = (1,0)]
  ```
  The output column is below. 
       a,b
  c,d  1,0  
  0,0 | 1 |
  0,1 | 0 | 
  1,1 | 1 | 
  1,0 | 0 |
  ```
   
[K-map Table Example End]
"""


RELATIONSHIP_EXTRACT_PROMPT="""
You are a Verilog RTL design expert with experience in determining the relationships between entities. The JSON structure contains a list of plans, signals, fsm_states and signal_examples for a digital design. Analyze the following JSON structure to determine relationship between these entities according to the [Steps] provided.

```json
{json_struct}
```

[Steps]
1. For each plan in the JSON, determine which signals it implements/declares based on their descriptions. A single plan can implement multiple signals. If the plan doesn't implement any signal, leave it empty.
2. For each signal in the JSON, determine which fsm_states are influencing it based on their descriptions. A signal can be influenced by multiple fsm_states. If the signal doesn't gets impacted by any fsm_state, leave it empty.
3. For each signal in the JSON, determine if they have an example provided in the signal_examples list. A signal can have multiple examples. If the signal doesn't have any example, leave it empty.

"""


PLAN_EXTRACT_PROMPT="""
You are a Verilog RTL designer. You make a final plan draft for the designing a digital block. You will be provided with the description of the module along with a JSON structure containing a list of initial plan draft along with its relationships catagorized as `signals`, `fsm_states` and `examples. This json structure is retireved from a Knowledge Graph database representing the possible relationships of signals, fsm_states and example to the plan. 

Analyze the JSON structure carefully with the specification and create the a well elaborated final plan draft for the digital design. The final plan draft should be a list of plans in their respective order. Include the relevent information from the json into the plan.

   - You must remove the relationships which are not mentioned in the plan. Make the related information short and be able to cover the plan need.
   - You must include the relevent signals, if they are present for that plan.
   - You must include the relevent examples, if the examples of the signal are present for that plan.
   - You must include the relevent fsm_states, if the fsm_states are is present for that plan.

 You can use the relationships between the plans, signals, fsm_states and examples to make your decision.

[Module Description]
{spec}

[Plan-Relationship JSON]
```json
{json_struct}
```
"""

RTL_DESIGNER_SYSTEM_MESSAGE="""
You are a Verilog RTL designer that only writes code using correct Verilog syntax. Your task is to implement the remaining parts of the module based on the provided [Subtask] description.
When you make any change in the the code, you should ALWAYS run the `verilog_compilation_tool` to check the syntax. If any syntax error occurs, you should fix the code and rerun the `verilog_compilation_tool` again untill the compilation is successful.
You work with an RTL reviewer who will review your code after the compilation. Make the changed as the suggested by the rtl_reviewer.

You will receive the following inputs:
- The problem statement of the module.
- The previous implementation of the module (if any).
- The current subtask description.
- The current subtask reference from the problem statement.

You will be expected to:
- Implement the current subtask based on the provided description.
- Use the provided previous implementation (if any) as a reference and do not modify it.
- Ensure that the code adheres to the provided guidelines and rules.

[Hints]:
- For implementing kmap, you need to think step by step. Find the inputs corresponding to output=1, 0, and don't-care for each case. Categorized them and find if there are any combinations that can be simplify.  

[Rules]:
- Only write the verilog code for the [Current SubTask]. Don't generate code without defined in the [Current SubTask].
- Don't change or modify the code in [Previous Module Implementation].
- Return the written verilog log code with Previous Module Implementation. 
- Declare all ports and signals as logic.
- Don't use state_t to define the parameter. Use `localparam` or Use 'reg' or 'logic' for signals as registers or Flip-Flops.
- Don't generate duplicated signal assignments or blocks.
- Define the parameters or signals first before using them.
- Not all the sequential logic need to be reset to 0 when reset is asserted.    
- for combinational logic, you can use wire assign (i.e., assign wire = a ? 1:0;) or always @(*).
- for combinational logic with an always block do not explicitly specify the sensitivity list; instead use always @(*).
- For 'if' block, you must use begin and end as below.
  [if example]
  if (done) begin
    a = b;
    n = q;
  end
  [if example end]

"""

RTL_REVIEWER_SYSTEM_MESSAGE="""
You are a RTL reviewer. You verify the subtasks and written verilog code from verilog_engineer. Identify the mismatches of the module description, subtask and written verilog code. Suggest `rtl_designer` a plan to modify code with bulletins. You can not suggest modification of the Module input and output ports. If the provided Verilog code correctly implements the subtask requirement, you have to notify the user to proceed to the next subtask.
"""

RTL_DESIGNER_EXAMPLES="""
Follow the examples below to understand how to write the code.
The examples are not related to the task you are working on.

[Example Begin]

### Problem

I would like you to implement a module named TopModule with the following
interface. All input and output ports are one bit unless otherwise
specified.

 - input  clk
 - input  reset
 - input  in (8 bits)
 - output out (8 bits)

The module should implement an 8-bit registered incrementer. The 8-bit
input is first registered and then incremented by one on the next cycle.

Assume all sequential logic is triggered on the positive edge of the
clock. The reset input is active high synchronous and should reset the
output to zero.

### Solution

```verilog
module TopModule
(
  input  logic       clk,
  input  logic       reset,
  input  logic [7:0] in,
  output logic [7:0] out
);

  // Sequential logic

  logic [7:0] reg_out;

  always @( posedge clk ) begin
    if ( reset )
      reg_out <= 0;
    else
      reg_out <= in;
  end

  // Combinational logic

  logic [7:0] temp_wire;

  always @(*) begin
    temp_wire = reg_out + 1;
  end

  // Structural connections

  assign out = temp_wire;
endmodule
```

### Problem

I would like you to implement a module named TopModule with the following
interface. All input and output ports are one bit unless otherwise
specified.

 - input  clk
 - input  reset
 - input  in
 - output out

The module should implement a finite-state machine that takes as input a
serial bit stream and outputs a one whenever the bit stream contains two
consecutive one's. The output is one on the cycle _after_ there are two
consecutive one's.

Assume all sequential logic is triggered on the positive edge of the
clock. The reset input is active high synchronous and should reset the
finite-state machine to an appropriate initial state.

### Solution

```verilog
module TopModule
(
  input  logic clk,
  input  logic reset,
  input  logic in,
  output logic out
);

  // State enum

  localparam STATE_A = 2'b00;
  localparam STATE_B = 2'b01;
  localparam STATE_C = 2'b10;

  // State register

  logic [1:0] state;
  logic [1:0] state_next;

  always @(posedge clk) begin
    if ( reset ) begin
      state <= STATE_A;
    end else begin
      state <= state_next;
    end
  end

  // Next state combinational logic

  always @(*) begin
    state_next = state;
    case ( state )
      STATE_A: state_next = ( in ) ? STATE_B : STATE_A;
      STATE_B: state_next = ( in ) ? STATE_C : STATE_A;
      STATE_C: state_next = ( in ) ? STATE_C : STATE_A;
    endcase
  end

  // Output combinational logic

  always @(*) begin
    out = 1'b0;
    case ( state )
      STATE_A: out = 1'b0;
      STATE_B: out = 1'b0;
      STATE_C: out = 1'b1;
    endcase
  end

endmodule
```

[Example End]
"""

RTL_DESIGNER_PROMPT="""
[Problem Statement]
{spec}

[Previous Implementation]
```verilog
{code}
```

[Subtask]
{subtask}
"""

RTL_DEBUGGER_SYSTEM_MESSAGE = """
You are tasked with writing Verilog code as an RTL designer, ensuring both syntax correctness and functional verification through simulations.

Begin by coding in Verilog while adhering strictly to the given constraints and guidelines. Use the verilog_simulation_tool to verify both the syntax and functionality of your design.

**Instructions to fix compile errors:**
1. After running the simulation tool, if the syntax check fails (Compile Failed), revise the Verilog code to correct syntax errors.
2. Re-run the verilog_simulation_tool after each modification.
3. Repeat these steps until the code passes both syntax and functional checks.

**Instructions to fix functional errors:**
1. Ensure that the compilation is successful before proceeding.
2. Examine the simulation log to identify the time of the first mismatch and the mismatched signals.
3. Determine the signals and time window to trace, ensuring enough cycles are visualized before and after the mismatch.
4. Analyze dependencies of the mismatched signals within the Verilog code.
5. Use waveform_trace_tool to plot input and output signals, mismatched signals, and their dependencies.
6. Examine the waveform to identify the mismatch's root cause.
7. If necessary, plot additional signals using the waveform_trace_tool.
8. Continue until the root cause is identified, then rectify the bug and re-run verilog_simulation_tool.
9. Repeat these steps until the functional checks pass.

# Constraints

- Avoid using typedef enum in the Verilog code.
- Do not use $display or $finish in module implementation.
- The testbench is immutable.
- Declare all ports as logic and use wire or reg within the block.
- For registers or flip-flops, use reg or logic; do not use state_t.
- Utilize wire assign or always @(*) for combinational logic.
- Do not explicitly declare sensitivity lists in always blocks; use always @(*) instead.
- Prevent duplicate signal assignments or blocks.

# Guidelines

- Provide the full path of signals based on the testbench code when using waveform_trace_tool.
- Resolve failures sequentially; do not proceed to subsequent failures without addressing the current one.
- Assume the testbench's correctness; no modifications are allowed.
- Compare DUT outputs with reference model outputs if a reference model exists.
- Restrict tracing to input/output ports of reference modules; internal signals are off-limits.
- Clock signals should be visualized per tick, representing the clock's positive edge.

# Recommended Flow

Write verilog code --> verilog_simulation_tool --> waveform_trace_tool (repeat this until bug located with 100 percent confidence) --> Fix bug in code --> Back to step 1
"""


RTL_DEBUGGER_PROMPT="""
[Target Module Description]
### Problem 
{spec}

[Completed Verilog Module]
```verilog
{code}
```

[Verilog Testbench]
```systemverilog
{tb_code}
```

Run the simulation and fix bugs if any.
"""

from spec2plan import spec2plan
from plan2graph import plan2graph
from graph2tasks import graph2tasks
from tasks2rtl import generate_rtl
from verify_rtl import verify_rtl
from utils import equally_formatted, load_checkpoint, save_checkpoint, ensure_checkpoint_dir
import chainlit as cl
import json
import os

@cl.set_starters
async def set_starters():
    return [
        cl.Starter(
            label="Prob115_shift18",
            message="PROB_ID=Prob115_shift18",
        ),
        cl.Starter(
            label="Prob118_history_shift",
            message="PROB_ID=Prob118_history_shift",
        ),
        cl.Starter(
            label="Prob129_ece241_2013_q8",
            message="PROB_ID=Prob129_ece241_2013_q8",
        ),
        cl.Starter(
            label="Prob139_2013_q2bfsm",
            message="PROB_ID=Prob139_2013_q2bfsm",
        ),
        cl.Starter(
            label="Prob141_count_clock",
            message="PROB_ID=Prob141_count_clock",
        ),
        cl.Starter(
            label="Prob144_conwaylife",
            message="PROB_ID=Prob144_conwaylife",
        ),
        cl.Starter(
            label="Prob148_2013_q2afsm",
            message="PROB_ID=Prob148_2013_q2afsm",
        ),
        cl.Starter(
            label="Prob149_ece241_2013_q4",
            message="PROB_ID=Prob149_ece241_2013_q4",
        ),
        cl.Starter(
            label="Prob151_review2015_fsm",
            message="PROB_ID=Prob151_review2015_fsm",
        ),
        cl.Starter(
            label="Prob153_gshare",
            message="PROB_ID=Prob153_gshare",
        ),
        cl.Starter(
            label="Prob154_fsm_ps2data",
            message="PROB_ID=Prob154_fsm_ps2data",
        ),
        cl.Starter(
            label="Prob155_lemmings4",
            message="PROB_ID=Prob155_lemmings4",
        ),
        cl.Starter(
            label="not gate",
            message="PROB_ID=Prob005_notgate",
        ),
        cl.Starter(
            label="mux 2to1",
            message="PROB_ID=Prob022_mux2to1",
        ),
        cl.Starter(
            label="combinational gates",
            message="PROB_ID=Prob087_gates",
        ),
        cl.Starter(
            label="debug code",
            message="PROB_ID=Prob132_always_if2",
        )
    ]

@cl.on_chat_start
async def on_chat_start():
    cl.user_session.set("counter", 0)
    task_list = cl.TaskList()
    task_list.status = "Running..."

    task1 = cl.Task(title='spec2plan', status=cl.TaskStatus.READY)
    await task_list.add_task(task1)

    task2 = cl.Task(title='plan2graph', status=cl.TaskStatus.READY)
    await task_list.add_task(task2)

    task3 = cl.Task(title='graph2tasks', status=cl.TaskStatus.READY)
    await task_list.add_task(task3)

    task4 = cl.Task(title='tasks2rtl', status=cl.TaskStatus.READY)
    await task_list.add_task(task4)

    task6 = cl.Task(title='verify_rtl', status=cl.TaskStatus.READY)
    await task_list.add_task(task6)
    await task_list.send()

    cl.user_session.set("task_list", task_list)
    cl.user_session.set("tasks", [task1, task2, task3, task4, task6])

async def update_task(task_num, done=False):
    if task_num == 6:
        _,task_list = cl.user_session.get("tasks")[0], cl.user_session.get("task_list")
        if done:
            task_list.status = "Done..."
        else:
            task_list.status = "Failed..."
        await task_list.send()

    else:
        task,task_list = cl.user_session.get("tasks")[task_num-1], cl.user_session.get("task_list")

        if not done:
            task.status = cl.TaskStatus.RUNNING
            await task_list.send()
        else:
            task.status = cl.TaskStatus.DONE
            await task_list.send()

@cl.on_message
async def main(message):
    counter = cl.user_session.get("counter")
    counter += 1
    cl.user_session.set("counter", counter)

    content = message.content
    if "PROB_ID" in content:
        spec_id = content.split("PROB_ID=")[1]
        spec_file = f"./verilog-eval-v2/{spec_id}_prompt.txt"
        with open(spec_file, 'r') as f:
            spec = f.read()
        testbench_file = f"./verilog-eval-v2/{spec_id}_test.sv"
        reference_file = f"./verilog-eval-v2/{spec_id}_ref.sv"
        use_dataset_tb = True
        await code_flow(spec_id,spec,spec_file,testbench_file,reference_file,use_dataset_tb)
        return

    
    elif counter == 1:
        await cl.Message(content="Welcome to `RTL-pilot` chat. Please type your `spec` to get started generating it's RTL.").send()
        return
    
    else:
        import datetime
        now = datetime.datetime.now()
        spec_id = 'custom_' + now.strftime("%d%m%y_%H%M")
        spec = content
        spec_file = None
        testbench_file = None
        reference_file = None
        use_dataset_tb = False
        await code_flow(spec_id,spec,spec_file,testbench_file,reference_file,use_dataset_tb)
        return

async def code_flow(spec_id,spec,spec_file,testbench_file,reference_file,use_dataset_tb):
    await cl.Message(content=equally_formatted("Putting agents to work"),elements=[cl.Image(name="agents", path='./images/agents.jpeg', display="page")]).send()

    work_dir = f"./work/{spec_id}"
    if not os.path.exists(work_dir):
        os.makedirs(work_dir)

    #try:
    # Step 1: spec2plan
    print("Running spec2plan...")
    await update_task(task_num=1)
    await cl.Message(content=equally_formatted("Running spec2plan")).send()
    plan = await cl.make_async(load_checkpoint)('plan.json', spec_id)
    if plan is None:
        plan = await cl.make_async(spec2plan)(spec)
        await cl.make_async(save_checkpoint)(plan, 'plan.json', spec_id) #save_checkpoint(plan, 'plan.json', spec_id)
    await cl.Message(content=equally_formatted("Plan Generated: plan"), elements=[cl.Text(name="plan", content=json.dumps(plan, indent=4).__str__(), display="page", language="python")]).send()    
    await cl.Message(content=equally_formatted("Exiting spec2plan")).send()
    await update_task(task_num=1, done=True)

    # Step 2: plan2graph
    print("Running plan2graph...")
    await update_task(task_num=2)
    await cl.Message(content=equally_formatted("Running plan2graph")).send()
    graph = await cl.make_async(load_checkpoint)('graph.json', spec_id) #if load_checkpoint('graph.json', spec_id):
    if graph is None:
        async with cl.Step(name='plan2graph', type='llm') as step:
            graph = await cl.make_async(plan2graph)(spec, plan) #plan2graph(spec, plan)
        await cl.make_async(graph.export_graph)(os.path.join(ensure_checkpoint_dir(spec_id),'graph.json')) 
        await cl.make_async(graph.visualize_graph)(os.path.join(ensure_checkpoint_dir(spec_id), 'verilog_knowledge_graph.png'))
        
    await cl.Message(content=equally_formatted("Graph Generated: graph"), elements=[cl.Image(name="graph", path=os.path.join(ensure_checkpoint_dir(spec_id), 'verilog_knowledge_graph.png'), display="page")]).send()
    await cl.Message(content=equally_formatted("Exiting plan2graph")).send()
    await update_task(task_num=2, done=True)


    # Step 3: graph2tasks
    print("Running graph2tasks...")
    await update_task(task_num=3)
    await cl.Message(content=equally_formatted("Running graph2tasks")).send()
    tasks = await cl.make_async(load_checkpoint)('tasks.json', spec_id) #if load_checkpoint('tasks.json', spec_id):
    if tasks is None:
        async with cl.Step(name='graph2tasks', type='llm') as step:
            tasks = await cl.make_async(graph2tasks)(spec, graph) #graph2tasks(spec, graph)
        await cl.make_async(save_checkpoint)(tasks, 'tasks.json', spec_id)
        cl.run_sync(cl.Message(content=equally_formatted("Tasks Generated: tasks"), elements=[cl.Text(name="tasks", content="\n".join(tasks), display="page")]).send())
    else:
        cl.run_sync(cl.Message(content=equally_formatted("Tasks Generated: tasks"), elements=[cl.Text(name="tasks", content=json.dumps(tasks, indent=4), display="page", language="python")]).send())

    cl.run_sync(cl.Message(content=equally_formatted("Exiting graph2tasks")).send())
    await update_task(task_num=3, done=True)

    # Step 4: generate_rtl
    print("Running tasks2rtl...")
    await update_task(task_num=4)
    await cl.Message(content=equally_formatted("Running tasks2rtl")).send()

    code = await cl.make_async(load_checkpoint)('TopModule_int.v', spec_id) #if load_checkpoint('code.json', spec_id):
    interface = await cl.make_async(load_checkpoint)('interface.v', spec_id) #if load_checkpoint('interface.json', spec_id):
    
    if code is None or interface is None:
        code, interface = await cl.make_async(generate_rtl)(spec, tasks, work_dir)
        await cl.make_async(save_checkpoint)(code, 'TopModule_int.v', spec_id)
        await cl.make_async(save_checkpoint)(interface, 'interface.v', spec_id)

    await cl.Message(content=equally_formatted("Code Generated: code"), elements=[cl.Text(name="code", content=code, display="page", language="verilog")]).send()
    await cl.Message(content=equally_formatted("Interface Generated: interface"), elements=[cl.Text(name="interface", content=interface, display="page", language="verilog")]).send()
    await cl.Message(content=equally_formatted("Exiting tasks2rtl")).send()
    await update_task(task_num=4, done=True)

    if use_dataset_tb:
        print("Using the TB and Golden RTL from dataset...")
        await cl.Message(content=equally_formatted("Using the Golden RTL and TBfrom dataset")).send()

        with open(testbench_file, "r") as f:
            tb_code = f.read()
        with open(reference_file, "r") as f:
            golden_rtl_code = f.read()

        reference_rtl_path = reference_file

        await cl.Message(content=equally_formatted("TB Generated: tb"), elements=[cl.Text(name="tb", content=tb_code, display="page", language="verilog")]).send()
        await cl.Message(content=equally_formatted("Golden RTL Used: golden_rtl"), elements=[cl.Text(name="golden_rtl", content=golden_rtl_code, display="page", language="verilog")]).send()

    else:
        tb_code = ""
        reference_rtl_path = ""

    # Step 5: verify_rtl
    print("Running verify_rtl...")
    await update_task(task_num=5)
    await cl.Message(content=equally_formatted("Running verify_rtl")).send()

    is_pass, code, tb = await cl.make_async(verify_rtl)(spec, code, interface, reference_rtl_path, tb_code, use_dataset_tb, work_dir)
    await cl.make_async(save_checkpoint)(tb, 'tb.sv', spec_id)
    
    if is_pass:
        await cl.Message(content=equally_formatted("Correct RTL Generated: code"), elements=[cl.Text(name="code", content=code, display="page", language="verilog")]).send()
    else:
        await cl.Message(content=equally_formatted("Buggy RTL Generated: code"), elements=[cl.Text(name="code", content=code, display="page", language="verilog")]).send()

    await cl.Message(content=equally_formatted("Exiting verify_rtl")).send()
    await update_task(task_num=5, done=True)
    await update_task(task_num=6, done=True)
    #except Exception as e:
    #    print(f"Error in RTL generation pipeline: {str(e)}")


# if __name__ == '__main__':
#     main()


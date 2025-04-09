from spec2plan import spec2plan
from plan2graph import plan2graph
from graph2tasks import graph2tasks
from tasks2rtl import generate_rtl
from verify_rtl import verify_rtl
import os
import argparse
from utils import VerilogKnowledgeGraph, save_checkpoint, load_checkpoint, ensure_checkpoint_dir

    
def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='RTL Generation Pipeline with Checkpoints')
    parser.add_argument('--spec-id', required=True,
                        help='Unique identifier for the specification (used for checkpoint directory)')
    parser.add_argument('--start-from', choices=['spec2plan', 'plan2graph', 'graph2tasks', 'generate_rtl', 'verify_rtl'], 
                        help='Start pipeline from specified checkpoint stage')
    parser.add_argument('--spec-file', help='Path to spec file to use as input')
    parser.add_argument('--testbench-file', help='Path to testbench file for verification')
    parser.add_argument('--reference-file', help='Path to reference file for verification')
    return parser.parse_args()

def main():
    args = parse_arguments()
    spec_id = args.spec_id
    spec = None
    
    # If starting from the beginning and spec file is provided, load and save it to checkpoint
    if args.spec_file and os.path.exists(args.spec_file):
        with open(args.spec_file, 'r') as f:
            spec = f.read()
        # Save spec to checkpoint for future runs
        save_checkpoint(spec, 'spec.txt', spec_id)
    else:
        # Try to load spec from checkpoint if not provided
        spec = load_checkpoint('spec.txt', spec_id)
        if spec is None and args.start_from != 'generate_rtl':  # Only generate_rtl might not need the original spec
            print(f"Error: No spec file provided and no spec checkpoint found for {spec_id}")
            return

    try:
        # Step 1: spec2plan
        if args.start_from in [None, 'spec2plan']:
            if spec is None:
                print("Error: Cannot run spec2plan without a specification")
                return
            print("Running spec2plan...")
            plan = spec2plan(spec)
            save_checkpoint(plan, 'plan.json', spec_id)
        else:
            # Load plan from checkpoint
            plan = load_checkpoint('plan.json', spec_id)
            if plan is None:
                print(f"Error: Could not load plan checkpoint for {spec_id}")
                return

        # Step 2: plan2graph
        if args.start_from in [None, 'spec2plan', 'plan2graph']:
            print("Running plan2graph...")
            graph = plan2graph(spec, plan)
            graph.export_graph(filename=os.path.join(ensure_checkpoint_dir(spec_id), 'graph.json'))
        else:
            graph_path = os.path.join(ensure_checkpoint_dir(spec_id), 'graph.json')
            graph = VerilogKnowledgeGraph.load_from_json(graph_path)
            if not graph or not hasattr(graph, 'G') or graph.G.number_of_nodes() == 0:
                print(f"Error: Could not load graph checkpoint from {graph_path}")
                return

        # Step 3: graph2tasks
        if args.start_from in [None, 'spec2plan', 'plan2graph', 'graph2tasks']:
            print("Running graph2tasks...")
            tasks = graph2tasks(spec, graph)
            save_checkpoint(tasks, 'tasks.json', spec_id)
        else:
            tasks = load_checkpoint('tasks.json', spec_id)
            if tasks is None:
                print(f"Error: Could not load tasks checkpoint for {spec_id}")
                return

        # Step 4: generate_rtl
        if args.start_from in [None, 'spec2plan', 'plan2graph', 'graph2tasks', 'generate_rtl']:
            print("Running generate_rtl...")
            code = generate_rtl(spec, tasks)
            save_checkpoint(code, 'TopModule_int.v', spec_id)
        else:
            code = load_checkpoint('TopModule_int.v', spec_id)
            if code is None:
                print(f"Error: Could not load code checkpoint for {spec_id}")
                return

        if not os.path.exists(args.testbench_file):
            print(f"Error: Testbench file not found at {args.testbench_file}")
            return
            
        if not os.path.exists(args.reference_file ):
            print(f"Error: Reference file not found at {args.reference_file }")
            return
        
        with open(args.testbench_file, "r") as f:
            tb_code = f.read()

        # Step 5: verify_rtl
        print("Running verify_rtl...")
        is_pass, code = verify_rtl(spec, code, tb_code, args.reference_file )
        if is_pass:
            save_checkpoint(code, 'TopModule.v', spec_id)
        else:
            save_checkpoint(code, 'TopModule_buggy.v', spec_id)
        
    except Exception as e:
        print(f"Error in RTL generation pipeline: {str(e)}")
    

if __name__ == '__main__':
    main()


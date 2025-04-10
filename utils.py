import json
import subprocess
import os
import re
import shutil
from typing import Any, Dict, List, Tuple
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from vcdvcd import VCDVCD, binary_string_to_hex, StreamParserCallbacks


def ensure_checkpoint_dir(spec_id=None):
    """Create checkpoints directory if it doesn't exist"""
    base_dir = 'checkpoints'
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)
    
    if spec_id:
        checkpoint_dir = os.path.join(base_dir, spec_id)
        if not os.path.exists(checkpoint_dir):
            os.makedirs(checkpoint_dir)
        return checkpoint_dir
    
    return base_dir


def save_checkpoint(data, filename, spec_id=None):
    """Save data to checkpoint file"""
    checkpoint_dir = ensure_checkpoint_dir(spec_id)
    filepath = os.path.join(checkpoint_dir, filename)
    
    if filename.endswith('.json'):
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    else:
        with open(filepath, 'w') as f:
            f.write(data)
    
    return filepath


def load_checkpoint(filename, spec_id=None):
    """Load data from checkpoint file"""
    checkpoint_dir = ensure_checkpoint_dir(spec_id)
    filepath = os.path.join(checkpoint_dir, filename)
    
    if not os.path.exists(filepath):
        return None
    
    if filename.endswith('.json'):
        with open(filepath, 'r') as f:
            return json.load(f)
    else:
        with open(filepath, 'r') as f:
            return f.read()


def extract_json_from_markdown(md_string):
    """Extract JSON content from a markdown code block"""
    match = re.search(r"```json\s*([\s\S]*?)\s*```", md_string)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None
    return None


class VerilogKnowledgeGraph:
    """Class for managing Verilog knowledge in a graph structure"""
    
    def __init__(self, json_data, json_connections):
        """Initialize the knowledge graph from JSON specification data."""
        self.data = json_data if isinstance(json_data, dict) else json.loads(json_data)
        self.connections = json_connections if isinstance(json_connections, dict) else json.loads(json_connections)
        self.G = nx.DiGraph()
        self.relationship_types = ["IMPLEMENTS", "STATETRANSITION", "EXAMPLES"]
        
    def build_graph(self):
        """Build the knowledge graph with nodes and relationships."""
        self._add_nodes()
        self._connect_nodes()
        return self.G
    
    def _add_nodes(self):
        """Add all entities as nodes to the graph."""
        for i in self.data.get("plans", []):
            self.G.add_node(i.get("name"), type="plan", description=i.get("description"))
        for i in self.data.get("signals", []) or []:
            self.G.add_node(i.get("name"), type="signal", description=i.get("description"))
        for i in self.data.get("fsm_states", []) or []:
            self.G.add_node(i.get("name"), type="fsm_state", description=i.get("description"))
        for i in self.data.get("signal_examples", []) or []:
            self.G.add_node(i.get("name"), type="example", description=i.get("description"))
    
    def _connect_nodes(self):
        """Connect nodes with appropriate relationships"""
        for i in self.connections['plans']:
            for j in (i['signals'] or []):
                self.G.add_edge(i['name'], j, relationship="IMPLEMENTS")
        
        for i in self.connections['signals']:
            for j in (i['fsm_states'] or []):
                self.G.add_edge(i['name'], j, relationship="STATETRANSITION")
            for j in (i['examples'] or []):
                self.G.add_edge(i['name'], j, relationship="EXAMPLES")
    
    @classmethod
    def load_from_json(cls, json_path):
        """
        Load a graph from a previously exported JSON file.
        
        Args:
            json_path (str): Path to the JSON file containing exported graph data
            
        Returns:
            VerilogKnowledgeGraph: A new instance with the restored graph
        """
        with open(json_path, 'r') as f:
            graph_data = json.load(f)
        
        # Create an empty instance
        instance = cls({}, {})
        
        # Create a new DiGraph and populate it
        instance.G = nx.DiGraph()
        for node in graph_data['nodes']:
            instance.G.add_node(node['id'], type=node['type'], description=node['description'])
        
        for edge in graph_data['edges']:
            instance.G.add_edge(edge['source'], edge['target'], relationship=edge['relationship'])
        
        return instance
    
    def visualize_graph(self, figsize=(12, 10)):
        """Visualize the knowledge graph."""
        plt.figure(figsize=figsize)
        
        # Generate positions
        pos = nx.spring_layout(self.G, seed=42)
        
        # Color nodes by type
        node_colors = []
        for node in self.G.nodes():
            node_type = self.G.nodes[node]["type"]
            if node_type == "plan":
                node_colors.append("lightblue")
            elif node_type == "signal":
                node_colors.append("lightgreen")
            elif node_type == "fsm_state":
                node_colors.append("lightcoral")
            elif node_type == "example":
                node_colors.append("gray")
        
        # Draw nodes
        nx.draw_networkx_nodes(self.G, pos, node_color=node_colors, node_size=800, alpha=0.8)
        
        # Draw node labels
        node_labels = {node: node for node in self.G.nodes()}
        nx.draw_networkx_labels(self.G, pos, labels=node_labels, font_size=8)
        
        # Draw edges with different colors based on relationship
        edge_colors = {
            "IMPLEMENTS": "green",
            "STATETRANSITION": "red",
            "EXAMPLES": "gray"
        }
        
        for rel_type, color in edge_colors.items():
            rel_edges = [(u, v) for u, v, d in self.G.edges(data=True) if d.get("relationship") == rel_type]
            if rel_edges:
                nx.draw_networkx_edges(self.G, pos, edgelist=rel_edges, edge_color=color, 
                                      arrows=True, arrowsize=15, width=1.5, alpha=0.7)
        
        # Add legend
        node_legend_elements = [
            Line2D([0], [0], marker='o', color='w', markerfacecolor='lightblue', markersize=10, label='Plan'),
            Line2D([0], [0], marker='o', color='w', markerfacecolor='lightgreen', markersize=10, label='Signal'),
            Line2D([0], [0], marker='o', color='w', markerfacecolor='lightcoral', markersize=10, label='FSM State'),
            Line2D([0], [0], marker='o', color='w', markerfacecolor='gray', markersize=10, label='Example')
        ]
        
        edge_legend_elements = [
            Line2D([0], [0], color='green', lw=2, label='IMPLEMENTS'),
            Line2D([0], [0], color='red', lw=2, label='STATETRANSITION'),
            Line2D([0], [0], color='gray', lw=2, label='EXAMPLES')
        ]
        
        plt.legend(handles=node_legend_elements + edge_legend_elements, loc='upper right')
        
        plt.title("Verilog Specification Knowledge Graph")
        plt.axis("off")
        plt.tight_layout()
        plt.savefig("verilog_knowledge_graph.png", dpi=300, bbox_inches="tight")
        plt.show()
    
    def export_graph(self, filename="verilog_knowledge_graph.json"):
        """Export the graph to a JSON format."""
        data = {
            "nodes": [],
            "edges": []
        }
        
        # Export nodes
        for node, attrs in self.G.nodes(data=True):
            node_data = {
                "id": node,
                "type": attrs.get("type", "unknown"),
                "description": attrs.get("description", "")
            }
            data["nodes"].append(node_data)
        
        # Export edges
        for src, dst, attrs in self.G.edges(data=True):
            edge_data = {
                "source": src,
                "target": dst,
                "relationship": attrs["relationship"]
            }
            data["edges"].append(edge_data)
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        return data
    
    def query_graph(self, query_type, entity_type=None, entity_name=None, relationship_type=None, direction=None):
        """Query the knowledge graph for specific information."""
        results = []
        
        if query_type == "list_entities":
            # List all entities of a specific type
            for node, attrs in self.G.nodes(data=True):
                if attrs.get("type") == entity_type:
                    results.append({
                        "name": node,
                        "description": attrs.get("description", "")
                    })
        
        elif query_type == "get_relationships":
            # Outgoing relationships
            if direction is None or direction == "out":
                for _, target, attrs in self.G.out_edges(entity_name, data=True):
                    if relationship_type is None or attrs["relationship"] == relationship_type:
                        results.append({
                            "source": entity_name,
                            "target": target,
                            "relationship": attrs["relationship"]
                        })
            
            # Incoming relationships
            if direction is None or direction == "in":
                for source, _, attrs in self.G.in_edges(entity_name, data=True):
                    if relationship_type is None or attrs["relationship"] == relationship_type:
                        results.append({
                            "source": source,
                            "target": entity_name,
                            "relationship": attrs["relationship"]
                        })
        
        return results

    def bfs_relationship_recursive(self, q=[[{'source': 'root', 'target': '', 'relationship': ''}]], depth=1, level=0):
        """Recursively perform breadth-first search on relationships"""
        if level == depth:
            return q
        else:
            q.append([rel for i in q[-1] for rel in self.query_graph("get_relationships", entity_name=i['target'], direction="out")])
            return self.bfs_relationship_recursive(q, depth, level+1)

    def bfs_relationship(self, root='', depth=1):
        """Start a BFS from a root node to explore relationships"""
        return self.bfs_relationship_recursive(q=[[{'source': 'root', 'target': root, 'relationship': ''}]], depth=depth, level=0)


class CustomCallback(StreamParserCallbacks):
    """Custom callback for VCD signal tracing"""
    def __init__(self, signals=None, offset=0, window=20, clock=None):
        self.signals = signals or {}
        self.window = window
        self.counter = 0
        self.offset = offset
        self.time_values = []
        self.signal_data = {}  # Store signal values by signal name
        self.clock = clock     # Store the clock signal reference
        self.clock_id = None   # Will store the clock's identifier code
        self.vcd_signals = []  # Store all signals in the VCD file
        self.errors = []       # Store error messages

    def enddefinitions(self, vcd, signals, cur_sig_vals):
        """Process VCD signal definitions"""
        self.vcd_signals = {sig.split('[')[0]: vcd.references_to_ids[sig] for sig in vcd.signals}

        # Initialize signal_data dictionary
        for sig in self.signals:
            if sig in self.vcd_signals:
                self.signal_data[sig] = []
            else:
                self.errors.append(f"Error: Signal '{sig}' not found in waveform.")
        
        # Get clock identifier if clock is specified
        if self.clock and self.clock in vcd.signals:
            self.clock_id = vcd.references_to_ids[self.clock]

    def time(self, vcd, time, cur_sig_vals):
        """Process values at a specific time point"""
        self.counter += 1

        if time > self.offset + self.window or time < self.offset:
            return

        if vcd.signal_changed:
            # Only record values when clock is 1 or when no clock is specified
            if not self.clock_id or (self.clock_id in cur_sig_vals and cur_sig_vals[self.clock_id] == '0'):
                # Store the time value
                self.time_values.append(str(time))
                
                # Store the signal values
                for key in self.signal_data.keys():
                    value = cur_sig_vals[self.vcd_signals[key]]
                    self.signal_data[key].append(binary_string_to_hex(value))

    def format_transposed_output(self):
        """Format signal data in a tabular representation"""
        output = []
        for error in self.errors:
            output.append(error)
        output.append('')

        if not self.signal_data:
            return "\n".join(output)

        # Define column width for better alignment
        first_col_width = max(len(key) for key in self.signal_data.keys()) # Width for the first column (signal names)
        max_signal_width = max(len(item) for sublist in self.signal_data.values() for item in sublist)
        max_time_width = max(len(str(time)) for time in self.time_values)
        time_col_width = max(max_signal_width, max_time_width) + 2   # Width for each time value column
        
        # Create header row with time values
        header = f"{'time':<{first_col_width}}"
        
        # Add time values with proper spacing
        for time_val in self.time_values:
            header += f"{time_val:>{time_col_width}}"
        output.append(header)
        
        # Create a row for each signal
        for signal_name, values in self.signal_data.items():
            row = f"{signal_name:<{first_col_width}}"
            
            # Add each value with proper spacing
            for value in values:
                row += f"{value:>{time_col_width}}"
            output.append(row)
        
        return "\n".join(output)


def get_traces(vcd_path: str, signals: List[str], offset: int = 0, window: int = 100, clock: str = "") -> str:
    """Get signal traces from a VCD file"""
    callback = CustomCallback(signals=signals, offset=offset, window=window, clock=clock)
    VCDVCD(vcd_path, callbacks=callback, store_tvs=False, only_sigs=False)
    
    return callback.format_transposed_output()


class VerilogToolKits:
    """Tools for Verilog analysis, compilation, and simulation"""
    
    def __init__(self, workdir: str = "./verilog_tool_tmp/"):
        # Directory structure
        self.workdir = workdir
        self.verilog_file_path = os.path.join(self.workdir, "test.sv")
        self.test_vpp_file_path = os.path.join(self.workdir, "test.vpp")
        self.wave_vcd_file_path = os.path.join(self.workdir, "wave.vcd")
        self.completed_verilog_file_path = os.path.join(self.workdir, "test.v")
        
        # Data state
        self.test_bench = ""
        self.ref_rtl_path = ""
        self.cur_graph_verilog = ""  # used to update the AST graph_tracer
        self.completed_verilog = ""
        self.spec = ""  # store the spec
        self.graph_tracer = None

    def get_work_paths(self) -> Dict[str, str]:
        """Get paths used by this toolkit"""
        return {
            'workdir': self.workdir,
            'verilog': self.completed_verilog_file_path,
            'test_sv': self.verilog_file_path,
            'wave': self.wave_vcd_file_path
        }

    def reset(self) -> None:
        """Reset the toolkit state"""
        self.test_bench = ""
        self.spec = ""
        self.cur_graph_verilog = ""
        self.completed_verilog = ""
        self.graph_tracer = None

    def load_test_bench(self, test_bench: str, task_id: str = 'Prob', spec: str = 'spec', write_file: bool = False) -> None:
        """Load a test bench and optionally write it to a file"""
        self.spec = spec
        self.test_bench = test_bench
        assert self.test_bench, "Test bench cannot be empty"
        
        if write_file:
            test_bench_filename = f"{task_id}.sv"
            with open(os.path.join(self.workdir, test_bench_filename), 'w') as f:
                f.write(self.test_bench)

    def load_ref_rtl_path(self, ref_rtl_path: str) -> None:
        """Set the reference RTL path"""
        self.ref_rtl_path = ref_rtl_path

    def write_verilog_file(self, task_id: str, num: int = 0, output_dir: str = None) -> Tuple[str, str]:
        """Write the current Verilog module to file"""
        if output_dir is None:
            output_dir = self.workdir
        
        generated_module = f"{task_id}_{num}.v"
        with open(os.path.join(output_dir, generated_module), 'w') as f:
            f.write(self.completed_verilog)
        
        generated_test_file = f"{task_id}_{num}.sv"
        with open(os.path.join(output_dir, generated_test_file), 'w') as f:
            f.write(f"{self.test_bench}\n{self.completed_verilog}")
        
        return generated_module, generated_test_file

    def check_functionality(self, vvp_output: str) -> bool:
        """Check if simulation results indicate correct functionality"""
        mismatches = None
        
        for line in vvp_output.splitlines():
            if re.match(r"^Mismatches:", line):
                print(line)
                mismatches = int(line.split()[1])
                break
            elif re.match(r"^Hint: Total mismatched samples is ", line):
                print(line)
                mismatches = int(line.split()[5])
                break

        print('mismatches =', mismatches)
        assert mismatches is not None, "Could not find mismatch information in output"
        
        return mismatches == 0

    def verilog_syntax_check_tool(self, completed_verilog: str) -> Tuple[bool, str]:
        """Check the syntax of Verilog code"""
        if "endmodule" not in completed_verilog:
            example_verilog_code = f"{completed_verilog} endmodule"
            return False, (f"[Error] the module is not completed! You need to write the Verilog module code with "
                          f"`module` in the beginning and `endmodule` in the end!\nBelow is the example:\n"
                          f"```verilog\n{example_verilog_code}\n```")
        
        completed_verilog = completed_verilog.strip()
        self.completed_verilog = completed_verilog  # record the latest verilog result

        with open(self.completed_verilog_file_path, 'w') as f:
            f.write(completed_verilog)
        
        cmd = f"iverilog -Wall -Winfloop -Wno-timescale -g2012 -s TopModule -o {self.test_vpp_file_path} {self.completed_verilog_file_path}"
        cmds = cmd.split()
        
        print(" ".join(cmds))
        try:
            outputs = subprocess.check_output(cmds, stderr=subprocess.STDOUT)
            outputs = outputs.decode("utf-8").splitlines()
        except subprocess.CalledProcessError as e:
            outputs = e.output.decode("utf-8").splitlines()

        # Compile failed if there's any output
        if outputs:
            error_msg = "\n".join(outputs)
            return False, f"[Compiled Failed Report]\n{error_msg}"

        return True, f"[Compiled Success Verilog Module]:\n```verilog\n{self.completed_verilog}\n```"

    def verilog_simulation_tool(self, completed_verilog: str) -> Tuple[bool, bool, str]:
        """Compile and simulate Verilog code"""
        print(f'running simulation tool in {self.workdir}')
        
        # Validate input and state
        assert self.test_bench, "Test bench must be loaded before simulation"
        
        if "endmodule" not in completed_verilog:
            example_verilog_code = f"{completed_verilog} endmodule"
            log = (f"[Error] the module is not completed! You need to write the Verilog module code with "
                   f"`module` in the beginning and `endmodule` in the end!\nBelow is the example:\n"
                   f"```verilog\n{example_verilog_code}\n```")
            return False, False, log
        
        # Prepare files
        num_tb_lines = len(self.test_bench.splitlines())
        completed_verilog = completed_verilog.strip()
        verilog_file = f"{self.test_bench}\n{completed_verilog}"
        self.completed_verilog = completed_verilog  # record the latest verilog result

        with open(self.verilog_file_path, 'w') as f:
            f.write(verilog_file)
        
        with open(self.completed_verilog_file_path, 'w') as f:
            f.write(completed_verilog)
        
        # Compile the Verilog file
        cmd = f"iverilog -Wall -Winfloop -Wno-timescale -g2012 -s tb -o {self.test_vpp_file_path} {self.verilog_file_path} {self.ref_rtl_path}"
        cmds = cmd.split()
        
        print(" ".join(cmds))
        try:
            outputs = subprocess.check_output(cmds, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            outputs = e.output

        outputs = outputs.decode("utf-8").splitlines()
        
        # Handle compilation errors
        if outputs:
            error_line_window = 5
            compiled_error = {}
            error_msg = ""

            for content in outputs:
                if not re.search(r'sv\:[\d+]', content):
                    error_msg += f"{content}\n"
                    continue
                    
                tmp = content.split(':')
                m_error_line = int(tmp[1])
                if m_error_line > num_tb_lines:
                    compiled_error[m_error_line] = " ".join(tmp[2:])
                else:
                    error_msg += f"{content}\n"
            
            # Format error messages with context
            if compiled_error:
                verilog_lines = verilog_file.splitlines()
                module_error_msg = ""
                
                for error_cnt, (m_error_line, error_text) in enumerate(compiled_error.items(), 1):
                    verilog_lines[m_error_line] = f"{verilog_lines[m_error_line]} ## Error line: {error_text} ## "
                    
                    # Show context around error
                    pre_lines = max(0, m_error_line - error_line_window)
                    post_lines = min(len(verilog_lines) - 1, m_error_line + error_line_window)
                    
                    module_error_msg += f"## Compiled Error Section {error_cnt} Begin ##\n\n"
                    module_error_msg += "\n".join(verilog_lines[pre_lines:post_lines+1]) + "\n"
                    module_error_msg += f"\n## Compiled Error Section {error_cnt} End ##\n\n"
            
                module_error_msg += error_msg
                return False, False, f"[Compiled Failed Report]\n{module_error_msg}"
            else:
                return False, False, f"[Compiled Failed Report]\n{error_msg}"

        # Run simulation
        if os.path.exists(self.wave_vcd_file_path):
            os.remove(self.wave_vcd_file_path)
            
        cmds = ["vvp", self.test_vpp_file_path]
        print(" ".join(cmds))
        outputs = subprocess.check_output(cmds, stderr=subprocess.DEVNULL).decode("utf-8")

        # Handle wave file
        if os.path.exists(os.getcwd() + "/wave.vcd"):
            shutil.move(os.getcwd() + "/wave.vcd", self.wave_vcd_file_path)

        # Check functional correctness
        if self.check_functionality(outputs):
            log = f"[Compiled Success]\n[Function Check Success]\n{outputs}"
            return True, True, log
        else:
            log = (f"[Compiled Success]\n[Function Check Failed]\n==Tool Output==\n{outputs}"
                   f"==Tool Output End==\n\n**Only focus on first point of failure in time. "
                   f"Please use the `waveform_trace_tool` around that time with window "
                   f"width of atleast 100 to check the waveform. Don't fix the code without "
                   f"running `waveform_trace_tool`.**")
            return True, False, log

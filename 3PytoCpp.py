import os
import io
import sys
import subprocess
import gradio as gr

# Replace with your Ollama model name (local model)
OLLAMA_MODEL = "llama3.2"  

# System message for context
system_message = (
    "You are an assistant that reimplements Python code in high performance C++ for an M2 Mac. "
    "Respond only with C++ code; use comments sparingly and do not provide any explanation other than occasional comments. "
    "The C++ response needs to produce an identical output in the fastest possible time."
)

def user_prompt_for(python_code):
    """Construct the user portion of the prompt."""
    return (
        "Rewrite this Python code in C++ with the fastest possible implementation that produces identical output in the least time. "
        "Respond only with C++ code; do not explain your work other than a few comments. "
        "Pay attention to number types to ensure no int overflows. Remember to #include all necessary C++ packages such as iomanip.\n\n"
        + python_code
    )

def write_output(cpp_code):
    """Write the final C++ code to 'optimized.cpp' after removing triple backticks."""
    clean_code = cpp_code.replace("```cpp", "").replace("```", "")
    with open("optimized.cpp", "w") as f:
        f.write(clean_code)

def stream_ollama(python_code):
    """
    Run Ollama synchronously using `ollama run` (as available in Ollama 3.2)
    and yield the full output. We now pass the prompt via the `input` parameter
    of communicate() to avoid I/O on a closed file.
    """
    prompt = system_message + "\n" + user_prompt_for(python_code)
    command = [
        "ollama",
        "run",
        OLLAMA_MODEL
    ]
    
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    try:
        # Pass the prompt as input to communicate
        output, err = process.communicate(input=prompt + "\n", timeout=300)
    except subprocess.TimeoutExpired:
        process.kill()
        output, err = process.communicate()
    
    if err.strip():
        print("Ollama Error:", err, file=sys.stderr)
    
    # Clean up code fences before yielding
    yield output.replace("```cpp\n", "").replace("```", "")

def optimize(python, model):
    """
    Based on the selected model (here, only "Ollama" is available for use with Ollama 3.2),
    call the conversion function and yield the result.
    """
    if model == "Ollama":
        result = stream_ollama(python)
    else:
        raise ValueError("Unknown or unsupported model")
    
    for stream_so_far in result:
        yield stream_so_far


def execute_python(code):
    """Execute Python code safely, capturing its output."""
    try:
        output_buffer = io.StringIO()
        sys.stdout = output_buffer
        exec(code)
    finally:
        sys.stdout = sys.__stdout__
    return output_buffer.getvalue()

def execute_cpp(code):
    """
    Write the code to 'optimized.cpp', compile it with Apple clang for M2,
    then run the resulting executable.
    """
    write_output(code)
    try:
        compile_cmd = [
            "clang++",
            "-Ofast",
            "-std=c++17",
            "-march=armv8.5-a",
            "-mtune=apple-m2",
            "-mcpu=apple-m2",
            "-o", "optimized",
            "optimized.cpp"
        ]
        subprocess.run(compile_cmd, check=True, text=True, capture_output=True)
        
        run_cmd = ["./optimized"]
        run_result = subprocess.run(run_cmd, check=True, text=True, capture_output=True)
        return run_result.stdout
    except subprocess.CalledProcessError as e:
        return f"An error occurred:\n{e.stderr}"

css = """
.python { background-color: #306998; }
.cpp { background-color: #050; }
"""

# Example Python code (replace with your own as needed)
python_hard = r'''
import time

def calculate(iterations, param1, param2):
    result = 1.0
    for i in range(1, iterations+1):
        j = i * param1 - param2
        result -= (1/j)
        j = i * param1 + param2
        result += (1/j)
    return result

start_time = time.time()
result = calculate(100_000_000, 4, 1) * 4
end_time = time.time()

print(f"Result: {result:.12f}")
print(f"Execution Time: {(end_time - start_time):.6f} seconds")
'''

with gr.Blocks(css=css) as ui:
    gr.Markdown("## Convert Python code to high-performance C++ using Ollama")
    
    with gr.Row():
        python_code = gr.Textbox(label="Python code:", value=python_hard, lines=10)
        cpp_code = gr.Textbox(label="C++ code:", lines=10)
    
    with gr.Row():
        # For Ollama 3.2, only the "Ollama" option is available.
        model_select = gr.Dropdown(["Ollama"], label="Select model", value="Ollama")
    
    with gr.Row():
        convert_btn = gr.Button("Convert code")
    
    with gr.Row():
        run_python_btn = gr.Button("Run Python")
        run_cpp_btn = gr.Button("Run C++")
    
    with gr.Row():
        python_out = gr.TextArea(label="Python result:", elem_classes=["python"])
        cpp_out = gr.TextArea(label="C++ result:", elem_classes=["cpp"])
    
    # Connect UI actions to functions
    convert_btn.click(optimize, inputs=[python_code, model_select], outputs=[cpp_code])
    run_python_btn.click(execute_python, inputs=[python_code], outputs=[python_out])
    run_cpp_btn.click(execute_cpp, inputs=[cpp_code], outputs=[cpp_out])

ui.launch(inbrowser=True)

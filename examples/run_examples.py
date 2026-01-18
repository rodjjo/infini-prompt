import os
import sys
import json
current_dir = os.path.dirname(__file__)
parent_dir = os.path.abspath(os.path.join(current_dir, '..'))

sys.path.append(parent_dir)
os.environ["PYTHONPATH"] = parent_dir 

from infini_prompt import generate_prompt

def main():
    # Define the path to the examples directory
    examples_dir = os.path.join(current_dir)

    # List all example files
    example_files = [f for f in os.listdir(examples_dir) if f.endswith('.txt')]
    generated_outputs = []
    for example_file in example_files:
        example_path = os.path.join(examples_dir, example_file)
        
        with open(example_path, 'r') as file:
            input_data = file.read()
        
        # Generate prompt using the inini_prompt library
        an_element_for_each_promt = ["first", "second", "third", "fourth", "fifth"]
        kwargs = {
            "my_argument": "Passed to the template",
            "follow-list-of-my_counting": "\n".join(an_element_for_each_promt)
        }
        prompt = generate_prompt(input_data, kwargs=kwargs, num_prompts=2, num_continues=1)
        for p in prompt:
            generated_outputs.append(p["output"])
        print(f"Example: {example_file}")
        print("Generated Prompt:")
        print(json.dumps(prompt, indent=2))
        print("-" * 40)
        print("\n")

    print("All Generated Outputs:")
    for output in generated_outputs:
        print(output, end="\n\n")
if __name__ == "__main__":
    main()

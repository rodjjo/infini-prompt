# Infini-Prompt Library

## Overview
The `infini-prompt` library is a powerful tool for generating dynamic prompts based on templates. It supports a wide range of operators to manipulate and customize the output. This README provides a comprehensive guide to using the `generate_prompt` function and explains each operator in detail.

---

## Installation
To use the `infini-prompt` library, clone the repository and install the required dependencies:

```bash
pip install https://github.com/rodjjo/infini-prompt.git
```

---

## Run a complete example:
```bash
python3 examples/run_examples.py
```

## Usage

### `generate_prompt` Function
The `generate_prompt` function is the core of the library. It takes a template and generates a prompt based on the provided data and operators.

#### Function Signature:
```python
def generate_prompt(
    template: dict, 
    seed: int = None, 
    enhance: bool = False,
    kwargs: dict = {},
    num_prompts: int = 1,
    num_continues: int = 0,
) -> dict:
```

#### Parameters:
- `template` (dict): The template containing the entrypoint and data.
- `seed` (int, optional): Seed for randomization to ensure reproducibility.
- `enhance` (bool, optional): Whether to enhance the prompt (not implemented yet).
- `kwargs` (dict, optional): Additional metadata or parameters.
- `num_prompts` (int, optional): Number of prompts to generate.
- `num_continues` (int, optional): Number of continuation prompts.

#### Example:
```python
from infini_prompt.prompt_generator import generate_prompt

template = {
    "entrypoint": "Hello {name}",
    "templates": {
        "data": {
            "name": "World"
        }
    }
}

result = generate_prompt(template, seed=42)
print(result["output"])  # Output: Hello World
```

---

## Operators
Operators are used within templates to perform various actions. Below is a detailed explanation of each operator.

### 1. **Equality Operators**
- **Syntax:** `{==:key|value|true_result|false_result}`
- **Description:** Compares the value of `key` with `value`. Returns `true_result` if they are equal, otherwise `false_result`.
- **Variants:** `==`, `=`, `equals`, `eq`

### 2. **Inequality Operators**
- **Syntax:** `{!=:key|value|true_result|false_result}`
- **Description:** Returns `true_result` if `key` is not equal to `value`.
- **Variants:** `!=`, `not_equals`, `neq`, `<>`

### 3. **Quantitative Operators**
- **Syntax:** `{>:key|value|true_result|false_result}`
- **Description:** Compares numeric values.
- **Variants:** `>`, `<`, `>=`, `<=`, `gt`, `lt`, `gte`, `lte`

### 4. **One-Of Operator**
- **Syntax:** `{one_of:opt1|opt2|opt3}`
- **Description:** Randomly selects one of the options.

### 5. **Static Operator**
- **Syntax:** `{$:key}`
- **Description:** Ensures the same value is used across multiple references.

### 6. **Exclusive Operator**
- **Syntax:** `{@:key}`
- **Description:** Ensures no repeats within the same template.

### 7. **Literal Operator**
- **Syntax:** `{#:text}`
- **Description:** Returns the literal text.

### 8. **Maybe Operator**
- **Syntax:** `{maybe:chance|text}`
- **Description:** Includes `text` with a given probability.

### 9. **Error Operator**
- **Syntax:** `{error:key|value}`
- **Description:** Triggers an error if `key` equals `value`.

### 10. **Coalesce Operator**
- **Syntax:** `{!:key1|key2|default}`
- **Description:** Returns the first non-empty value.

---

## Operator Reference Table

Below is a table summarizing all operators supported by the `infini-prompt` library. Each operator includes its name, description, and an example of usage.

| **Operator**       | **Description**                                                                 | **Example**                                                                 |
|---------------------|---------------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `==`, `=`, `equals`, `eq` | Compares if a key's value equals a specified value. Returns true or false results. | `{==:status\|active\|Welcome\|Goodbye}`                                 |
| `!=`, `not_equals`, `neq`, `<>` | Compares if a key's value does not equal a specified value. Returns true or false results. | `{!=:status\|inactive\|Active\|Inactive}`                               |
| `>`, `<`, `>=`, `<=`, `gt`, `lt`, `gte`, `lte` | Compares numeric values. Supports greater, less, and equality checks. | `{>:age\|18\|Adult\|Minor}`                                             |
| `one_of`, `choice`, `select`, `any`, `any_of`, `pick_one` | Randomly selects one option from a list of choices.                          | `{one_of:Red\|Blue\|Green}`                                              |
| `{@:key}`           | Ensures no repeats within the same template.                                    | `{@:fruit} {@:fruit}`                                                      |
| `{$:key}`           | Ensures the same value is used across multiple references.                     | `{$:color} and {$:color}`                                                  |
| `{#:text}`          | Returns the literal text provided.                                             | `{#:This is a literal string}`                                             |
| `{maybe:chance\|text}` | Includes text with a given probability.                                        | `{maybe:50\|Optional Text}`                                               |
| `{error:key\|value}` | Triggers an error if the key's value matches the specified value.              | `{error:key\|value}`                                                      |
| `{!:key1\|key2\|default}` | Returns the first non-empty value from the provided keys or default.          | `{!:key1\|key2\|default}`                                                |
| `{repeat:count\|text}` | Repeats the text a specified number of times.                                  | `{repeat:3\|Hello}`                                                       |
| `{track:name\|text}` | Tracks the resolved text under a specified name for later use.                | `{track:log\|Generated Text}`                                             |
| `{optional:key\|default}` | Returns the value of the key if it exists, otherwise returns the default.     | `{optional:username\|Guest}`                                              |
| `{in:key\|list\|true\|false}` | Checks if the key's value is in a comma-separated list.                     | `{in:fruit\|apple,banana\|Found\|Not Found}`                            |
| `{has:key\|substrings\|true\|false}` | Checks if the key's value contains all specified substrings.            | `{has:text\|hello,world\|Yes\|No}`                                      |
| `{case:key\|prefix\|default\|values}` | Matches the key's value against a list of cases and applies a prefix. | `{case:color\|is_\|unknown\|red,blue}`                                  |
| `{*:key}`           | Resolves the key dynamically and uses it to look up another value.             | `{*:{animal_key}}`                                                         |
| `{^:key\|exclude\|default}` | Selects a random value from a key, excluding specified values.               | `{^:fruit\|apple\|default}`                                              |
| `{comment:text}`    | Ignores the text and returns an empty string.                                  | `{comment:This is a comment}`                                              |
| `{//:text}`         | Same as `comment`, ignores the text.                                           | `{//:This is another comment}`                                             |

---

## Detailed Examples for Operators

### Equality Operators
```json
{
    "entrypoint": "{==:status|active|Welcome|Goodbye}",
    "templates": {
        "data": {
            "status": "active"
        }
    }
}
```

### Inequality Operators
```json
{
    "entrypoint": "{!=:status|inactive|Active|Inactive}",
    "templates": {
        "data": {
            "status": "active"
        }
    }
}
```

### Quantitative Operators
```json
{
    "entrypoint": "{>:age|18|Adult|Minor}",
    "templates": {
        "data": {
            "age": "20"
        }
    }
}
```

### One-Of Operator
```json
{
    "entrypoint": "{one_of:Red|Blue|Green}",
    "templates": {
        "data": {}
    }
}
```

### Static Operator
```json
{
    "entrypoint": "{$:color} and {$:color}",
    "templates": {
        "data": {
            "color": ["red", "blue", "green"]
        }
    }
}
```

### Exclusive Operator
```json
{
    "entrypoint": "{@:fruit} {@:fruit}",
    "templates": {
        "data": {
            "fruit": ["apple", "banana", "orange"]
        }
    }
}
```

### Literal Operator
```json
{
    "entrypoint": "{#:This is a literal string}",
    "templates": {
        "data": {}
    }
}
```

### Maybe Operator
```json
{
    "entrypoint": "{maybe:50|Optional Text}",
    "templates": {
        "data": {}
    }
}
```

### Error Operator
```json
{
    "entrypoint": "{error:key|value}",
    "templates": {
        "data": {
            "key": "value"
        }
    }
}
```

### Coalesce Operator
```json
{
    "entrypoint": "{!:key1|key2|default}",
    "templates": {
        "data": {
            "key1": "",
            "key2": "value"
        }
    }
}
```

### Repeat Operator
```json
{
    "entrypoint": "{repeat:3|Hello}",
    "templates": {
        "data": {}
    }
}
```

### Track Operator
```json
{
    "entrypoint": "{track:log|Generated Text}",
    "templates": {
        "data": {}
    }
}
```

### Optional Operator
```json
{
    "entrypoint": "{optional:username|Guest}",
    "templates": {
        "data": {
            "username": "John"
        }
    }
}
```

### In Operator
```json
{
    "entrypoint": "{in:fruit|apple,banana|Found|Not Found}",
    "templates": {
        "data": {
            "fruit": "apple"
        }
    }
}
```

### Has Operator
```json
{
    "entrypoint": "{has:text|hello,world|Yes|No}",
    "templates": {
        "data": {
            "text": "hello world"
        }
    }
}
```

### Case Operator
```json
{
    "entrypoint": "{case:color|is_|unknown|red,blue}",
    "templates": {
        "data": {
            "color": "red"
        }
    }
}
```

### Eval Operator
```json
{
    "entrypoint": "{*:{animal_key}}",
    "templates": {
        "data": {
            "animal_key": "dog",
            "dog": "a cute puppy"
        }
    }
}
```

### Except Operator
```json
{
    "entrypoint": "{^:fruit|apple|default}",
    "templates": {
        "data": {
            "fruit": ["apple", "banana", "orange"]
        }
    }
}
```

### Comment Operator
```json
{
    "entrypoint": "{comment:This is a comment}",
    "templates": {
        "data": {}
    }
}
```

### Slash Comment Operator
```json
{
    "entrypoint": "{//:This is another comment}",
    "templates": {
        "data": {}
    }
}
```

---

## Comprehensive Example Using All Operators

Below is a comprehensive example that demonstrates the use of all operators in a single template. This example showcases how the operators can work together to create a dynamic and complex prompt.

```json
{
    "entrypoint": "{==:status|active|{#:Welcome, {optional:username|Guest}! You have {repeat:3|{one_of:amazing|wonderful|great}} opportunities.}|{error:status|inactive}}",
    "templates": {
        "data": {
            "status": "active",
            "username": "John",
            "fruit": ["apple", "banana", "orange"],
            "color": ["red", "blue", "green"],
            "animal_key": "dog",
            "dog": "a loyal companion",
            "text": "hello world",
            "age": "25",
            "log": "",
            "color_case": "blue"
        },
        "logic": {
            "track": "{track:log|{#:Tracking this text}}",
            "maybe": "{maybe:50|This text appears 50% of the time.}",
            "exclusive": "{@:fruit} {@:fruit}",
            "static": "{$:color} and {$:color}",
            "quantitative": "{>:age|18|Adult|Minor}",
            "in_check": "{in:fruit|apple,banana|Found|Not Found}",
            "has_check": "{has:text|hello,world|Yes|No}",
            "case_check": "{case:color_case|is_|unknown|red,blue}",
            "eval": "{*:{animal_key}}",
            "except": "{^:fruit|apple|default}",
            "comment": "{comment:This is a comment}",
            "slash_comment": "{//:This is another comment}"
        }
    }
}
```

### Explanation:
1. **Equality Operator (`==`)**: Checks if the `status` is `active`. If true, it proceeds with the welcome message; otherwise, it triggers an error.
2. **Literal Operator (`{#:}`)**: Used to include static text like "Welcome" and "Tracking this text".
3. **Optional Operator (`{optional:}`)**: Includes the `username` if available; defaults to "Guest" otherwise.
4. **Repeat Operator (`{repeat:}`)**: Repeats the phrase "amazing", "wonderful", or "great" three times.
5. **One-Of Operator (`{one_of:}`)**: Randomly selects one of the options.
6. **Error Operator (`{error:}`)**: Triggers an error if the `status` is "inactive".
7. **Track Operator (`{track:}`)**: Tracks the resolved text for later use.
8. **Maybe Operator (`{maybe:}`)**: Includes text with a 50% probability.
9. **Exclusive Operator (`{@:}`)**: Ensures no repeats within the same template.
10. **Static Operator (`{$:}`)**: Ensures the same value is used across multiple references.
11. **Quantitative Operator (`{>:}`)**: Checks if the `age` is greater than 18.
12. **In Operator (`{in:}`)**: Checks if the `fruit` value is in the list "apple, banana".
13. **Has Operator (`{has:}`)**: Checks if the `text` contains "hello" and "world".
14. **Case Operator (`{case:}`)**: Matches the `color_case` value against a list of cases.
15. **Eval Operator (`{*:}`)**: Dynamically resolves the `animal_key` to "dog" and retrieves its value.
16. **Except Operator (`{^:}`)**: Selects a random value from `fruit`, excluding "apple".
17. **Comment Operators (`{comment:}` and `{//:}`)**: Ignores the text and returns an empty string.

This example demonstrates the flexibility and power of the `infini-prompt` library to handle complex templates with ease.
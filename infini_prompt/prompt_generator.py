import os
import json
import random
import typing
import time
import copy
import re
from tqdm import tqdm



class PromptError(Exception):
    pass

def enhance_prompt(prompt: str, enhancements: dict) -> str:
    # not implemented yet
    return prompt

ESCAPE_MAPPINGS = {
    "|": "&pipe;",
    "{": "&lbrace;",
    "}": "&rbrace;",
    ",": "&comma;",
    "&": "&amp;"
}
EQUAL_OPERATORS = ["==", "=", "equals", "eq"]
INEQUAL_OPERATORS = ["!=", "not_equals", "neq", "<>"]
GREATER_OPERATORS = [">", "gt"]
LESS_OPERATORS = ["<", "lt"]
GREATER_EQUAL_OPERATORS = [">=", "gte"]
LESS_EQUAL_OPERATORS = ["<=", "lte"]
EQUALITY_OPERATORS = EQUAL_OPERATORS + INEQUAL_OPERATORS
QUANTITATIVE_OPERATORS = GREATER_OPERATORS + LESS_OPERATORS + GREATER_EQUAL_OPERATORS + LESS_EQUAL_OPERATORS
ONE_OF_OPERATORS = ["one_of", "choice", "select", "any", "any_of", "pick_one"]
STORE_OPERATORS = ["set", "store", ":="]
REPEAT_OPERATORS = ["repeat", "x"]
MAYBE_OPERATORS = ["maybe", "?"]
IN_OPERATOR = ["in", "not_in"]
HAS_OPERATOR = ["has", "not_has"]
TRACK_OPERATORS = ["track", "tk"]
OPTIONAL_OPERATORS = ["optional", "opt"]
IGNORE_OPERATORS = ["ignore", "ign", "empty"]
COMMENT_OPERATORS = ["comment", "//"]
OPERATOR_CASE = "case"
OPERATOR_EVAL = "*"
OPERATOR_ERROR = "error"
OPERATOR_COALESCE = "!"
OPERATOR_EXCEPT = "^"
OPERATOR_LITERAL = "#"



def escape_special_characters(text: str) -> str:
    for char, escape_seq in ESCAPE_MAPPINGS.items():
        text = text.replace(char, escape_seq)
    return text

def unescape_special_characters(text: str) -> str:
    for char, escape_seq in ESCAPE_MAPPINGS.items():
        text = text.replace(escape_seq, char)
    return text


def click_args_to_kwargs(args: typing.List[str]) -> dict:
    """Converts a list of command-line arguments to a dictionary of keyword arguments."""
    kwargs = {}
    for arg in args:
        if '=' in arg:
            name, value = arg.split('=', 1)
            kwargs[name] = value
    return kwargs


def process_entrypoint_list(value: list) -> str:
    """
    Process entrypoint list format.
    
    :param value: The entrypoint value as a list
    :type value: list
    :return: The processed string
    :rtype: str

    Examples of valid formats:
    ["option1", "option2", "option3"] - random choice from strings
    [["part1_option1", "part1_option2"], ["part2_option1", "part2_option2"]] - concat random from each
    ["fixed_start", ["part1_option1", "part1_option2"], ["part2_option1", "part2_option2"]] - fixed + randoms
    """
    if not value:
        return ""
    if isinstance(value, str):
        return value
    
    all_elements_are_strings = all(isinstance(e, str) for e in value)
    all_elements_are_lists = all(isinstance(e, list) for e in value)
    first_element_is_string = isinstance(value[0], str) if value else False
    all_elements_after_first_are_lists = all(isinstance(e, list) for e in value[1:]) if len(value) > 1 else True

    if all_elements_are_strings:
        return random.choice(value)
    elif all_elements_are_lists:
        # we need to concatenate all random choices from each list in sequence into a string
        result_parts = []
        for element in value:
            chosen_part = process_entrypoint_list(element)
            result_parts.append(chosen_part)
        return " ".join(result_parts)
    elif first_element_is_string and all_elements_after_first_are_lists:
        result_parts = [value[0]]
        for element in value[1:]:
            chosen_part = process_entrypoint_list(element)
            result_parts.append(chosen_part)
        return " ".join(result_parts)
    else:
        raise PromptError("Invalid entrypoint list structure.")
            

def validate_bracets(prompt: str):
    # Check if all { and } are balanced, and give context if not
    stack = []
    for idx, char in enumerate(prompt):
        if char == '{':
            stack.append(idx)
        elif char == '}':
            if not stack:
                context_start = max(0, idx - 10)
                context_end = min(len(prompt), idx + 10)
                context = prompt[context_start:context_end]
                raise PromptError(f"Unmatched closing bracket '}}' in prompt near: '{context}'")
            stack.pop()
    if stack:
        # Unmatched opening bracket, use the first unmatched one
        idx = stack[-1]
        context_start = max(0, idx - 10)
        context_end = min(len(prompt), idx + 10)
        context = prompt[context_start:context_end]
        raise PromptError(f"Unmatched opening bracket '{{' in prompt near: '{context}'")


def eat_next_bracets(prompt: str) -> str:
    start_index = prompt.find('{')
    if start_index == -1:
        return ""
    stack = []
    for idx in range(start_index, len(prompt)):
        char = prompt[idx]
        if char == '{':
            stack.append(idx)
        elif char == '}':
            stack.pop()
            if not stack:
                return prompt[start_index + 1:idx]
    return ""


def select_normal(name: str, state: dict) -> str:
    # select one of the normal options from state data
    if "{" in name:
        return process_prompt(name, state)
    if name not in state["data"]:
        raise PromptError(f"Selection key '{name}' not found in state data.")
    options = state["data"][name]
    if isinstance(options, str):
        result = options
        if "{" in result:
            result = process_prompt(result, state)
        return result
    if not isinstance(options, list) or not options:
        raise PromptError(f"Selection key '{name}' must be a non-empty list.")
    choice = random.choice(options)
    if "{" in choice:
        choice = process_prompt(choice, state)
    return choice


def select_exclusive(name: str, state: dict, prefix: str= "") -> str:
    # select one of the exclusive options from state data
    if name not in state["data"]:
        raise PromptError(f"Exclusive selection key '{name}' not found in state data.")
    options = state["data"][name]
    if isinstance(options, str):
        return select_normal(name, state)
    if not isinstance(options, list) or not options:
        raise PromptError(f"Exclusive selection key '{name}' must be a non-empty list.")
    # lets create a copy of options to avoid modifying the original list
    data = options[:]
    # lets remove from data any options that were used in state usage
    name_prefix = prefix + name
    used_options = state.get("usage", {}).get(name_prefix, [])
    data = [opt for opt in data if opt not in used_options]
    
    if not data:
        # lets clean up the usage and use all options again
        state["usage"][name_prefix] = []
        data = options[:]
    options = data
    # now we can select a random choice from options
    choice = random.choice(options)
    # lets add the choice to the usage
    if "usage" not in state:
        state["usage"] = {}
    if name_prefix not in state["usage"]:
        state["usage"][name_prefix] = []
    state["usage"][name_prefix].append(choice)
    if "{" in choice:
        choice = process_prompt(choice, state)
    return choice

def select_static(name: str, state: dict, prefix="") -> str:
    # if the key is on the static dict, we return it directly
    if "static" not in state:
        state["static"] = {}
    data = state["static"]
    name_prefix = prefix + name
    if name_prefix in data:
        return data[name_prefix]
    # otherwise we select a normal option and store it in static
    result = select_normal(name, state)
    state["static"][name_prefix] = result
    return result

def operator_maybe(text: str, chance: int = 50) -> str:
    text = text.strip()
    if random.randint(1, 100) <= chance:
        return text
    return ""

def selector_except(key: str, exclude_key: str, state: dict, default: str) -> str:
    """Select a value from key excluding the value from exclude_key.
    Format: {^:key|exclude_key}
    """
    key = key.strip()
    exclude_key = exclude_key.strip()
    if key not in state["data"]:
        raise PromptError(f"Selection key '{key}' not found in state data.")
    if "," not in exclude_key and exclude_key not in state["data"]:
        raise PromptError(f"Exclude selection key '{exclude_key}' not found in state data.")
    options = state["data"][key]
    if isinstance(options, str):
        options = [options]
    if not isinstance(options, list):
        raise PromptError(f"Selection key '{key}' must be a list or string.")
    if not options:
        raise PromptError(f"Selection key '{key}' must be a non-empty list.")
    options = [
        opt if "{" not in opt else process_prompt(opt, state) for opt in options
    ]
    if "," in exclude_key:
        options_exclude = exclude_key.split(",")
    else:
        options_exclude = state["data"][exclude_key]
    if isinstance(options_exclude, str):
        options_exclude = [options_exclude]
    options_exclude = [
        opt if "{" not in opt else process_prompt(opt, state) for opt in options_exclude if opt.strip()
    ]
    filtered_options = [opt for opt in options if opt not in options_exclude]
    if not filtered_options:
        if '{' in default:
            default = process_prompt(default, state)
        return default
    return random.choice(filtered_options)


def operator_equals(key: str, compare_value: str, state: dict, value_if_true: str, value_if_false: str, negative=False) -> str:
    """Compare a key's value with a literal value.
    Format: {==:key|literal_value|true_result|false_result}
    """
    key = key.strip()
    compare_value = compare_value.strip()
    key_value = select_normal(key, state)
    if value_if_true is None:
        value_if_true = ""
    if value_if_false is None:
        value_if_false = ""
    if (key_value == compare_value) != negative:
        return value_if_true
    else:
        return value_if_false
    

def operator_greater(key: str, compare_value: str, state: dict, value_if_true: str, value_if_false: str, negative=False, exact=False) -> str:
    """Compare a key's value with a literal numeric value.
    Format: {>:key|literal_value|true_result|false_result}
    """
    key = key.strip()
    compare_value = compare_value.strip()
    key_value = select_normal(key, state)
    try:
        left_number = float(key_value)
        right_number = float(compare_value)
    except ValueError:
        raise PromptError(f"Cannot compare non-numeric values: '{key_value}' and '{compare_value}'")
    if exact:
        comparison_result = (left_number >= right_number)
    else:
        comparison_result = (left_number > right_number)
    if negative:
        comparison_result = not comparison_result
    return value_if_true if comparison_result else value_if_false


def operator_in(key: str, list_value: str, state: dict, value_if_true: str, value_if_false: str, negative=False) -> str:
    """Check if key's value is in a comma-separated list.
    Format: {in:key|comma_separated_list|true_result|false_result}
    """
    key = key.strip()
    list_value = list_value.strip()
    key_value = select_normal(key, state)
    # we split list_value by comma to get the list of values
    list_values = [v.strip() for v in list_value.split(",")]
    if value_if_true is None:
        value_if_true = ""
    if value_if_false is None:
        value_if_false = ""
    if (key_value in list_values) != negative:
        return value_if_true
    else:
        return value_if_false
    

def operator_has(key: str, substrings: str, state: dict, value_if_true: str, value_if_false: str, negative=False) -> str:
    """Check if key's value contains all the given substrings.
    Format: {has:key|comma_separated_substrings|true_result|false_result}
    """
    key = key.strip()
    substrings = substrings.strip()
    key_value = select_normal(key, state)
    substring_list = [v.strip() for v in substrings.split(",")]
    has_all = all(s in key_value for s in substring_list)
    if value_if_true is None:
        value_if_true = ""
    if value_if_false is None:
        value_if_false = ""
    if (has_all) != negative:
        return value_if_true
    else:
        return value_if_false
    
def operator_case(text: str, state: dict, prefix: str, default: str, case_values: list) -> str:
    # if the value is in case_values, we return prefix + value
    value = select_normal(text, state)
    for v in case_values:
       if v in value:
            return prefix + v
    return default

def operator_one_of(text: str, state: dict) -> str:
    # select one of the options from a pipe separated list
    options = [v.strip() for v in text.split("|")]
    if not options:
        return ""
    option = random.choice(options)
    if "{" in option:
        option = process_prompt(option, state)
    return option


def operator_repeat(text: str, count: int, state: dict) -> str:
    result = ""
    if count > 256:
        raise PromptError("Repeat operator count exceeds maximum of 256.")
    while count > 0:
        if "{" in text:
            part = process_prompt(text, state)
        else:
            part = text
        result += part
        count -= 1
    return result


def operator_store(key: str, text: str, state: dict, prefix: str="") -> str:
    # store a key in the statics in state
    if "static" not in state:
        state["static"] = {}
    if "{" in text:
        value = process_prompt(text, state)
    else:
        value = text
    state["static"][prefix + key] = value
    return ""


def operator_track(text: str, track_name: str, state: dict) -> str:
    # store a key in the tracking in state, return tex same text, after possible processing
    # we want to add the possibility to store the resolved part of the template inside a name, so we can take decisions on it later
    if "{" in text:
        text = process_prompt(text, state)
    state["data"][f"track_{track_name}"] = text
    return text

def optional_operator(key: str, default: str, state: dict) -> str:
    # if the key is not in data, return default
    if key not in state["data"]:
        if '{' in default:
            default = process_prompt(default, state)
        return default
    return select_normal(key, state)

def operator_error(text: str, compare_value: str, state: dict) -> str:
    # result in error if equals otherwise return empty
    key = text.strip()
    compare_value = compare_value.strip()
    key_value = select_normal(key, state)
    if key_value == compare_value:
        raise PromptError(f"Error operator triggered: {key_value} == {compare_value}")
    return ""

def operator_ignore(text: str, state: dict) -> str:
    if "{" in text:
        process_prompt(text, state)  # process for side effects
    # always return empty string
    return ""

def resolve_operator(text: str, state: dict) -> str:
    # state is a dictionary with 
    # data, static, regex, paths and usage keys
    if ":" not in text:
        if "|" in text:
            return operator_one_of(text, state)
        # simple state lookup
        key = text.strip()
        return select_normal(key, state)
    operator, _, argument = text.partition(":")
    if operator in ONE_OF_OPERATORS:
        return operator_one_of(argument, state)
    elif operator.endswith("@"):
        prefix = operator[:-1]
        return select_exclusive(argument.strip(), state, prefix=prefix)
    elif operator.endswith("$"):
        prefix  = operator[:-1]
        return select_static(argument.strip(), state, prefix=prefix)
    elif operator == OPERATOR_LITERAL:
        # return the argument as it is, if we have { or } inside, we process cause an error, as it is supposed to be a literal
        if "{" in argument or "}" in argument:
            raise PromptError(f"Literal operator '#' cannot contain '{{' or '}}' characters: '{argument}'")
        return argument
    elif operator == OPERATOR_ERROR:
        # Format: {error:key|compare_value}
        parts = argument.split("|")
        if len(parts) < 2:
            raise PromptError(f"Error operator requires key|value format: '{argument}'")
        key = parts[0].strip()
        compare_value = parts[1].strip()
        return operator_error(key, compare_value, state)
    elif operator in EQUALITY_OPERATORS:
        negative = operator in INEQUAL_OPERATORS
        # Format: {==:key|compare_value|true_result|false_result}
        parts = argument.split("|")
        if len(parts) < 2:
            raise PromptError(f"Equality operator requires at least key|value format: '{argument}'")
        key = parts[0].strip()
        compare_value = parts[1].strip()
        value_if_true = parts[2] if len(parts) > 2 else ""
        value_if_false = parts[3] if len(parts) > 3 else ""
        return operator_equals(key, compare_value, state, value_if_true, value_if_false, negative=negative)
    elif operator in QUANTITATIVE_OPERATORS:
        negative = operator in ["<", "lt", "<=", "lte"]
        exact = operator in [">=", "gte", "<=", "lte"]
        # Format: {>:key|compare_value|true_result|false_result}
        parts = argument.split("|")
        if len(parts) < 2:
            raise PromptError(f"Quantitative operator requires at least key|value format: '{argument}'")
        key = parts[0].strip()
        compare_value = parts[1].strip()
        value_if_true = parts[2] if len(parts) > 2 else ""
        value_if_false = parts[3] if len(parts) > 3 else ""
        return operator_greater(key, compare_value, state, value_if_true, value_if_false, negative=negative, exact=exact)
    elif operator in IN_OPERATOR:
        negative = operator == "not_in"
        # Format: {in:key|list_value|true_result|false_result}
        parts = argument.split("|")
        if len(parts) < 2:
            raise PromptError(f"In operator requires at least key|list format: '{argument}'")
        key = parts[0].strip()
        list_value = parts[1].strip()
        value_if_true = parts[2] if len(parts) > 2 else ""
        value_if_false = parts[3] if len(parts) > 3 else ""
        return operator_in(key, list_value, state, value_if_true, value_if_false, negative=negative)
    elif operator in HAS_OPERATOR:
        negative = operator == "not_has"
        # Format: {has:key|substrings|true_result|false_result}
        parts = argument.split("|")
        if len(parts) < 2:
            raise PromptError(f"Has operator requires at least key|substrings format: '{argument}'")
        key = parts[0].strip()
        substrings = parts[1].strip()
        value_if_true = parts[2] if len(parts) > 2 else ""
        value_if_false = parts[3] if len(parts) > 3 else ""
        return operator_has(key, substrings, state, value_if_true, value_if_false, negative=negative)
    elif operator == OPERATOR_CASE:
        prefix = ""
        default = ""
        case_values = []
        if "|" in argument:
            parts = argument.split("|")
            if len(parts) >= 2:
                prefix = parts[1]
            if len(parts) >= 3:
                default = parts[2]
            if len(parts) >= 4:
                case_values = [v.strip() for v in parts[3].split(",")]
        return operator_case(argument.partition("|")[0], state, prefix, default, case_values)
    elif operator == OPERATOR_EVAL:
        # Eval operator: resolve the argument (which may contain {}) first,
        # then use the result as a key to look up
        # {*:{animal}} -> resolves {animal} to "dog", then looks up "dog" in data
        solved_key = argument.strip()
        return select_normal(solved_key, state)
    elif operator == OPERATOR_COALESCE:
        # if the value is empty, it replaces it with the first non-empty value from the list
        parts = argument.split("|")
        if len(parts) < 2:
            raise PromptError(f"Coalesce operator requires at least one key|value format: '{argument}'")
        key = parts[0].strip()
        key_value = process_prompt(key, state)
        if key_value:
            return key_value
        for part in parts[1:]:
            part_value = process_prompt(part.strip(), state)
            if part_value:
                return part_value
        return ""
    elif operator.isdigit(): # OPERATOR INDEX
        index = int(operator)
        parts = argument.split("|")
        if len(parts) < 1:
            raise PromptError(f"Index operator requires at least key|default_value format: '{argument}'")
        key = parts[0].strip()
        default_value = parts[1] if len(parts) > 1 else ""
        if key not in state["data"]:
            raise PromptError(f"Index selection key '{key}' not found in state data.")
        options = state["data"][key]
        if type(options) == str:
            options = [options]
        if not isinstance(options, list):
            raise PromptError(f"Index selection key '{key}' must be a list.")
        if 0 <= index < len(options):
            choice = options[index]
            if "{" in choice:
                choice = process_prompt(choice, state)
            return choice
        else:
            return default_value
    elif operator == OPERATOR_EXCEPT:
        # Format: {^:key|exclude_value|default_value}
        parts = argument.split("|")
        if len(parts) < 2:
            raise PromptError(f"Except operator requires at least key|exclude_value format: '{argument}'")
        key = parts[0].strip()
        exclude_value = parts[1].strip()
        default_value = parts[2] if len(parts) > 2 else ""
        return selector_except(key, exclude_value, state, default_value)
    elif (operator in MAYBE_OPERATORS) or (operator.endswith("?")):
        # syntaxes: {maybe:chance|key} or {50?:key} or just {?:key} (50% chance) or {key?} (50% chance)
        chance = 50 
        argument = argument.strip()
        if argument.startswith("{"):
            argument = process_prompt(argument, state)
            return operator_maybe("{#:" + argument + "}", chance=chance)
        key_part = argument
        if "|" in argument:
            parts = argument.split("|")
            chance_part = parts[0].strip()
            key_part = parts[1].strip()
            if chance_part.isdigit():
                chance = int(chance_part)
            else:
                raise PromptError(f"Chance value must be an integer: '{chance_part}'")
        elif operator[:-1].isdigit():
            chance = int(operator[:-1])
        if "{" in key_part:
            key_part = process_prompt(key_part, state)
        return operator_maybe(key_part, chance=chance)
    elif (operator in REPEAT_OPERATORS):
        # syntaxes: {repeat:count|text} or {x:count|text}
        parts = argument.split("|")
        if len(parts) < 2:
            raise PromptError(f"Repeat operator requires count|text format: '{argument}'")
        count_part = parts[0].strip()
        text_part = parts[1]
        if not count_part.isdigit():
            raise PromptError(f"Repeat count must be an integer: '{count_part}'")
        count = int(count_part)
        return operator_repeat(text_part, count, state)
    elif operator in STORE_OPERATORS or any(operator.endswith(f",{op}") for op in STORE_OPERATORS):
        # syntaxes: {set:key|text} or {store:key|text} or {:=:key|text} or {prefix,set:key|text} or {prefix,store:key|text} or {prefix,:=:key|text}
        prefix = ""
        if "," in operator:
            prefix_part, _, store_op = operator.rpartition(",")
            prefix = prefix_part
            operator = store_op
        parts = argument.split("|")
        if len(parts) < 2:
            raise PromptError(f"Store operator requires key|text format: '{argument}'")
        key = parts[0].strip()
        text = parts[1]
        return operator_store(key, text, state, prefix=prefix)
    elif operator in TRACK_OPERATORS:
        # syntaxes: {track:name|text} or {tk:name|text}
        parts = argument.split("|")
        if len(parts) < 2:
            raise PromptError(f"Track operator requires name|text format: '{argument}'")
        track_name = parts[0].strip()
        text = parts[1]
        return operator_track(text, track_name, state)
    elif operator in OPTIONAL_OPERATORS:
        # syntaxes: {optional:key|default} or {opt:key|default}
        parts = argument.split("|")
        if len(parts) < 2:
            raise PromptError(f"Optional operator requires key|default format: '{argument}'")
        key = parts[0].strip()
        default = parts[1]
        return optional_operator(key, default, state)
    elif operator in IGNORE_OPERATORS:
        # syntaxes: {ignore:text} or {ign:text} or {empty:text}
        text = argument
        return operator_ignore(text, state)
    elif operator in COMMENT_OPERATORS:
        # syntaxes: {comment:text} or {//:text}
        # we just return empty string
        return ""
    else:
        raise PromptError(f"Unknown operator '{operator}' in prompt.")

def process_prompt(prompt: str, state: dict, inside_bracets=False) -> str:
    if inside_bracets and (prompt.startswith("comment:") or prompt.startswith("//:")):
        return ""
    result = prompt
    while "{" in result:
        inner_content = eat_next_bracets(result)
        if not inner_content:
            break
        processed = process_prompt(inner_content, state, inside_bracets=True)
        # Replace only the first occurrence to ensure proper ordering
        result = result.replace("{" + inner_content + "}", processed, 1)
    if inside_bracets:
        return resolve_operator(result, state).strip()
    return result.strip()

def postprocess_prompt(prompt: str, template: dict) -> str:
    # remove duplicate spaces
    prompt = re.sub(r'\s+', ' ', prompt)
    # strip leading and trailing spaces
    prompt = prompt.strip()
    # replace ". ." with "."
    prompt = prompt.replace(". .", ".")
    prompt = prompt.replace(", ,", ",")
    # remove spaces before punctuation
    prompt = re.sub(r'\s+([.!?,;:])', r'\1', prompt)
    # ensure exactly one space after commas
    prompt = re.sub(r',\s*', ', ', prompt)
    # template has a postproces key with a list of regex for replacements
    if "postprocess" in template:
        postprocess_list = template["postprocess"]
        if not isinstance(postprocess_list, list):
            raise PromptError("Template 'postprocess' key must be a list.")
        for item in postprocess_list:
            if not isinstance(item, dict):
                raise PromptError("Each item in 'postprocess' list must be a dictionary with 'pattern' and 'replacement' keys.")
            if "pattern" not in item or "replacement" not in item:
                raise PromptError("Each item in 'postprocess' list must contain 'pattern' and 'replacement' keys.")
            pattern = item["pattern"]
            replacement = item["replacement"]
            try:
                # If the replacement contains {1}, {2}, etc., use re.sub with a function to support group references
                if re.search(r'\{(\d+)\}', replacement):
                    prompt = re.sub(
                        pattern,
                        lambda m: re.sub(
                            r'\{(\d+)\}',
                            lambda g: m.group(int(g.group(1))) if m.lastindex and int(g.group(1)) <= m.lastindex else '',
                            replacement
                        ),
                        prompt,
                        flags=re.IGNORECASE
                    )
                else:
                    prompt = re.sub(pattern, replacement, prompt, flags=re.IGNORECASE)
            except re.error as e:
                raise PromptError(f"Invalid regex pattern '{pattern}' in postprocess: {e}")
    return prompt


def preprocess_template(template: dict, kwargs: dict = {}) -> dict:
    # regex patterns from kwargs are stored in template.templates.regex
    if "templates" not in template:
        return template
    templates_tmp = template["templates"]
    data = templates_tmp.get("data", {})

    preproc = templates_tmp.get("preprocess", []) or []
    if not isinstance(preproc, list):
        raise PromptError("Template 'preprocess' key must be a list.")

    if "text" in kwargs:
        meta_text = kwargs["text"]
        for regex_value in preproc:
            if not isinstance(regex_value, dict):
                raise PromptError("Each item in 'preprocess' list must be a dictionary with 'pattern' and 'replacement' keys.")
            if "pattern" not in regex_value or "replacement" not in regex_value:
                raise PromptError("Each item in 'preprocess' list must contain 'pattern' and 'replacement' keys.")
            pattern = regex_value.get("pattern", "")
            replacement = regex_value.get("replacement", "")
            try:
                # If the replacement contains {1}, {2}, etc., use re.sub with a function to support group references
                if re.search(r'\{(\d+)\}', replacement):
                    meta_text = re.sub(
                        pattern,
                        lambda m: re.sub(
                            r'\{(\d+)\}',
                            lambda g: m.group(int(g.group(1))) if m.lastindex and int(g.group(1)) <= m.lastindex else '',
                            replacement
                        ),
                        meta_text,
                        flags=re.IGNORECASE
                    )
                else:
                    meta_text = re.sub(pattern, replacement, meta_text, flags=re.IGNORECASE)
            except re.error as e:
                raise PromptError(f"Invalid regex pattern '{pattern}' in preprocess: {e}")
        kwargs["meta_text"] = meta_text
        kwargs["text"] = meta_text

    # regex has the sintax {"field_name": "pattern"}
    # we look at all keys in kwargs that has the name "field_name" capture all groups from the pattern and store them in template.templates.data with the key "meta_regex_field_name"
    # in a string if we only have one group, or in a list if we have multiple groups
    if "regex" not in template["templates"]:
        return template
    regex_data = templates_tmp.get("regex", {})
    for field_name, pattern in regex_data.items():
        if "text" in kwargs:
            value = kwargs["text"]
            match = re.match(pattern, value)
            if not match:
                data[f"meta_regex_{field_name}"] = ""
                continue
            groups = match.groups()
            if len(groups) == 1:
                data[f"meta_regex_{field_name}"] = str(groups[0])
            else:
                data[f"meta_regex_{field_name}"] = [str(g) for g in groups]
        else:
            data[f"meta_regex_{field_name}"] = ""

    templates_tmp["data"] = data
    template["templates"].update(templates_tmp)
    return template


def include_templates(template: dict, kwargs: dict, included_files: set = None) -> dict:
    # if template has "include" key, we import the templates from imported_templates into template.templates.data
    if included_files is None:
        included_files = set()
    if "includes" not in template:
        return template
    include_list = template["includes"]
    if not isinstance(include_list, list):
        raise PromptError("Template 'includes' key must be a list.")
    for include_path in include_list:
        # the path has the syntax "/path/to/directory|file_name.json|file_name2.json" 
        # if | is not present, we assume the whole path is a single file
        if '|' in include_path:
            dir_path, *file_names = include_path.split('|')
            if '~' in dir_path:
                dir_path = os.path.expanduser(dir_path)
            elif not os.path.isabs(dir_path):
                # use current directory as base
                dir_path = os.path.abspath(os.path.join(os.getcwd(), dir_path))
            else:
                dir_path = os.path.abspath(os.path.expanduser(dir_path))
        else:
            dir_path = include_path
            if '~' in dir_path:
                dir_path = os.path.expanduser(dir_path)
            dir_path = os.path.abspath(dir_path)
            dir_path = os.path.dirname(dir_path)
            file_names = [os.path.basename(dir_path)]
        for file_name in file_names:
            file_path = os.path.join(dir_path, file_name)
            abs_file_path = os.path.abspath(file_path)
            if abs_file_path in included_files:
                raise PromptError(f"Circular reference detected when including '{abs_file_path}'.")
            included_files.add(abs_file_path)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    included_template = json.load(f)
            except Exception as e:
                raise PromptError(f"Failed to load included template file '{file_path}': {e}")
            if "templates" in included_template and "data" in included_template["templates"]:
                # lets validate the included template first
                included_template = initialize_template(included_template, kwargs)
                included_template = include_templates(included_template, kwargs, included_files)
                for key, value in included_template["templates"]["data"].items():
                    # We only import keys that do not exist in the current template already exists
                    if key not in template["templates"]["data"]:
                        template["templates"]["data"][key] = value
            # lets include the includes of the included template as well
    return template


def initialize_template(template: dict, kwargs: dict = {}) -> dict:
    if "templates" not in template:
        template["templates"] = {}
    if "data" not in template["templates"]:
        template["templates"]["data"] = {}

    # template.data keys cannot store "meta_" keys
    for key in template["templates"]["data"].keys():
        if key.startswith(("meta_", "track_")):
            raise PromptError(f"Template data key '{key}' cannot start with 'meta_' or 'track_'. These prefixes are reserved.")
    
    # kwargs can not contains "regex_" keys
    for key in kwargs.keys():
        if key.startswith("regex_"):
            raise PromptError(f"Argument key '{key}' cannot start with 'regex_'. This prefix is reserved.")

    template = preprocess_template(template, kwargs)
    template = include_templates(template, kwargs)

    # lets validate brace in all template data strings
    for key, value in template.get("templates", {}).get("data", {}).items():
        if isinstance(value, str):
            validate_bracets(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    validate_bracets(item)  

    return template

def detect_entrypoint_type(entrypoint: typing.Union[str, list, dict]) -> str:
    if isinstance(entrypoint, str):
        return "string"
    elif isinstance(entrypoint, list):
        return "list"
    elif isinstance(entrypoint, dict):
        has_text_key = "text" in entrypoint
        any_dict_keys = False
        for k in entrypoint.keys():
            v = entrypoint[k]
            if isinstance(v, dict):
                any_dict_keys = True
                break
        if has_text_key or any_dict_keys:
            return "tree_of_tags"
        return "dict"
    else:
        raise PromptError("Invalid entrypoint type.")


def resolve_tree_of_tags(entrypoint: dict, kwargs: dict) -> str:
    if "text" not in entrypoint:
        raise PromptError("Tree of tags entrypoint must contain a 'text' key.")
    if not kwargs.get("meta_tags_path"):
        raise PromptError("No 'meta_tags_path' provided in kwargs for tree of tags entrypoint.")
    # lets split tags path by "\n" to get a list of paths
    tags_paths = kwargs["meta_tags_path"].split("\n")
    # now we have a list of paths like ["tag1/tag2", "tag3/tag4"]
    # now create a list of lists of tags
    tags_paths = [path.strip().split("/") for path in tags_paths if path.strip()]
    text_list = []  
    for tags in tags_paths:
        # lets search the full path in the entrypoint tree
        current_node = entrypoint   
        found = True
        for tag in tags:
            if tag in current_node:
                current_node = current_node[tag]
            else:
                found = False
                break
        if found:
            text_list.append(current_node["text"])
    return "\n".join(text_list)


def ensure_template_dict(template: typing.Union[str, dict]) -> dict:
    if isinstance(template, dict):
        return template
    elif not isinstance(template, str):
        raise Exception("Template must be a dictionary or a string.")
    template = template.strip()
    # lets check if it starts with "{"
    if template.startswith("{"):
        try:
            template_dict = json.loads(template)
            return template_dict
        except Exception as e:
            pass # lets treat it like normal text file with json block inside, below. Maybe it just started with {template_key} text + json block after
       
    # lets split this string into a list of lines 
    # we are going to have something like:
    # This is a normal text file 
    # ```json
    # {
    #   "templates": {
    #       "data": {
    #           "key1": "value1",
    #           "key2": "value2"
    #       }
    #   }
    # }
    # ```
    # all the text outside the ```json ... ``` is the entrypoint text that we be added to the extracted json at the field "entrypoint"
    lines = template.splitlines()
    inside_json_block = False
    inside_template_block = False
    current_template_key = None
    json_lines = []
    template_lines = []
    entrypoint_lines = []
    templates_to_set = {}
    code_block_found = False
    for line in lines:
        stripped_line = line.strip()
        if stripped_line.startswith("```json"):
            if code_block_found:
                raise Exception("Multiple JSON code blocks found in template string.")
            inside_json_block = True
            code_block_found = True
            inside_template_block = False
            json_lines = []
            continue
        elif stripped_line.startswith("```template."):
            if inside_json_block:
                raise Exception("Template blocks must be before JSON block.")
            if inside_template_block:
                # finish previous template block
                content = "\n".join(template_lines).strip()
                templates_to_set[current_template_key] = content
                template_lines = []
            # start new template block
            key_part = stripped_line[len("```template.") : ].strip()
            current_template_key = key_part
            inside_template_block = True
            template_lines = []
            continue
        elif stripped_line.startswith("```") and (inside_json_block or inside_template_block):
            if inside_template_block:
                content = "\n".join(template_lines).strip()
                templates_to_set[current_template_key] = content
                inside_template_block = False
                current_template_key = None
                template_lines = []
            elif inside_json_block:
                inside_json_block = False
            continue
        if inside_json_block:
            json_lines.append(line)
        elif inside_template_block:
            template_lines.append(line)
        else:
            entrypoint_lines.append(line)
    if inside_json_block or inside_template_block:
        raise Exception("Unclosed code block in template string.")
    code_block_content = "\n".join(json_lines).strip()
    entrypoint_content = "\n".join(entrypoint_lines).strip()
    if not code_block_content:
        raise Exception("No JSON code block found in template string.")
    try:
        template_dict = json.loads(code_block_content)
    except Exception as e:
        raise Exception(f"Failed to parse JSON code block in template string: {e}")
    if entrypoint_content:
        template_dict["entrypoint"] = entrypoint_content
    else:
        raise Exception("No entrypoint content found outside JSON code block in template string.")
    # now, set the templates
    if "templates" not in template_dict:
        template_dict["templates"] = {}
    if "data" not in template_dict["templates"]:
        template_dict["templates"]["data"] = {}
    for key, value in templates_to_set.items():
        template_dict["templates"]["data"][key] = value
    return template_dict


def generate_prompt_no_except(
        template: dict, 
        seed: int = None, 
        enhance: bool=False,
        kwargs: dict = {},
        num_prompts: int = 1,
        num_continues: int = 0,
) -> dict:
    try:
        return generate_prompt(
            template=template,
            seed=seed,
            enhance=enhance,
            kwargs=kwargs,
            num_prompts=num_prompts,
            num_continues=num_continues,
        )
    except PromptError as e:
        return {
            "error": str(e)
        }

def generate_prompt(
        template: dict, 
        seed: int = None, 
        enhance: bool=False,
        kwargs: dict = {},
        num_prompts: int = 1,
        num_continues: int = 0,
) -> dict:
    template = ensure_template_dict(template)
    kwargs = copy.deepcopy(kwargs)
    if seed is None:
        seed = int(time.time() * 1000) + random.randint(0, 1 << 30)
    if num_prompts < 1:
        num_prompts = 1
    if num_prompts > 1000:
        num_prompts = 1000
    if num_continues < 0:
        num_continues = 0
    if num_continues > 10:
        num_continues = 10

    # if continue > 0, we can not allow wkars keys starting with meta_last_ because they would interfere with the continuation logic

    include_lists = []

    key_list = list(kwargs.keys())
    for key in key_list:  # use list to avoid modification during iteration
        if key.startswith("meta_"):
            raise PromptError(f"Argument key '{key}' cannot start with 'meta_'. This prefix is reserved for metadata.")
        if num_continues > 0 and key.startswith("meta_last_"):
            raise PromptError(f"Argument key '{key}' cannot start with 'meta_last_' when using continuation. This prefix is reserved for continuation logic.")
        if key.startswith("follow-list-of-"):
            value = kwargs[key]
            del kwargs[key]
            if not isinstance(value, str):
                raise PromptError(f"Argument key '{key}' must be a string when using multiple prompts.")
            name = key[len("follow-list-of-"):]
            values = []
            for v in value.split("\n"):
                v = v.strip()
                if v:
                    values.append(v)
            if values:
                include_lists.append((name, values))

    total_prompts = num_prompts * (num_continues + 1)
    current_prompt = 0
    result = []
    if total_prompts > 1:
        progress = tqdm(total=total_prompts, desc="Generating Prompts", unit="prompt")
    else:
        progress = None
    meta_lasts = {}
    for p_number in range(num_prompts):
        if include_lists:
            for name, values in include_lists:
                index = p_number % len(values)
                kwargs[f"current_{name}"] = values[index]
        for pass_number in range(num_continues + 1):
            kwargs["pass_number"] = str(pass_number)
            kwargs.update(meta_lasts)
            current_template = copy.deepcopy(template)
            generated = _generate_prompt_implementation(
                current_template,
                seed=seed + current_prompt,
                enhance=enhance,
                kwargs=kwargs,
            )
            kwargs_copy = copy.deepcopy(kwargs)
            # lets remove meta_last_ keys from kwargs_copy and remove the prefix current_ 
            current_keys = list(kwargs_copy.keys())
            for key in current_keys:
                if key.startswith("meta_last_"):
                    del kwargs_copy[key]
                if key.startswith("current_"):
                    new_key = key[len("current_"):]
                    kwargs_copy[new_key] = kwargs_copy[key]
                    del kwargs_copy[key]
            kwargs_copy["gen_pass_number"] = pass_number
            kwargs_copy["gen_prompt_number"] = p_number

            response = {
                "generation_info": kwargs_copy,
                **generated
            }
            result.append(response)
            current_prompt += 1
            if progress:
                progress.update(1)
            if num_continues > 0:
                # lets take all statics from the last generated prompt and store them in kwargs with meta_last_ prefix
                last_prompt = result[-1]
                for key, value in last_prompt.get("statics", {}).items():
                    if key.startswith("meta_last_"):
                        continue
                    meta_lasts[f"meta_last_{key}"] = value
                # we also store the last output as meta_last_output
                meta_lasts["meta_last_output"] = last_prompt.get("output", "")

    if progress:
        progress.close()

    if len(result) == 1:
        result = result[0]
    return result

def _generate_prompt_implementation(
        template: dict, 
        seed: int = None, 
        enhance: bool=False,
        kwargs: dict = {},
) -> dict:
    """
    Generates a prompt based on the provided template and seed.
    Args:
        template (dict): The template data for generating the prompt.
        seed (int, optional): Random seed for reproducibility. Defaults to None.
    Returns:
        str: The generated prompt.
    """
    if seed is None or seed < 1:
        seed = int(time.time() * 1000) + random.randint(0, 1 << 30)
    random.seed(seed)

    kwargs_processed = {}
    for key, value in kwargs.items():
        # lets assert all parameters are string only type
        if not isinstance(value, str):
            raise PromptError(f"Argument key '{key}' must be of type string. Found type: {type(value)}")
        if "regex_" in key:
            raise PromptError(f"Argument key '{key}' cannot contain 'regex_'. This prefix is reserved.")
        if key.startswith("meta_"):
            # lets remove the meta_ prefix for processing
            kwargs_processed[key[len("meta_"):]] = escape_special_characters(value)
        else:
            kwargs_processed[key] = escape_special_characters(value)
    kwargs = kwargs_processed

    template = initialize_template(template, kwargs)
    
    entrypoint = template.get("entrypoint", "")
    entrypoint_type = detect_entrypoint_type(entrypoint)
    if entrypoint_type == "list":
        entrypoint = process_entrypoint_list(entrypoint)
    elif entrypoint_type == "tree_of_tags":
        entrypoint = resolve_tree_of_tags(entrypoint, kwargs)
    elif entrypoint_type == "dict":
        entrypoint_selector = kwargs.get("entrypoint_selector", None)
        if not entrypoint_selector:
            raise PromptError("No entrypoint_selector provided for dict entrypoint selection.")
        # entrypoint selector is just a string with any content, we iterate all keys from the dict and see if the selector matches any key
        # basically we split the keys by space and check if the selector contains all the words in the key in the provided order
        # example: key = "goo morn", selector = "good morning everyone" -> matches because goo and morn are in selector and were found one after the other
        matched_key = None
        for key in entrypoint.keys():
            key_parts = key.split()
            current_index = 0
            match = True
            for part in key_parts:
                found_index = entrypoint_selector.find(part, current_index)
                if found_index == -1:
                    match = False
                    break
                current_index = found_index + len(part)
            if match:
                matched_key = key
                break
        if not matched_key:
            raise PromptError(f"No matching entrypoint found for selector: {entrypoint_selector}")
        entrypoint = entrypoint[matched_key]
        if isinstance(entrypoint, list):
            entrypoint = process_entrypoint_list(entrypoint)
    elif not isinstance(entrypoint, str):
        raise PromptError("Invalid entrypoint format in template.")

    if entrypoint is None:
        raise PromptError("Entrypoint is None after processing.")
    
    if type(entrypoint) is not str:
        raise PromptError("Entrypoint must be a string after processing.")
    entrypoint = entrypoint.strip()

    if not entrypoint:
        raise PromptError("Entrypoint is empty after processing.")

    validate_bracets(entrypoint)

    # lets store all keys from kwargs into template.templates.data with meta_ prefix
    data_field = template["templates"]["data"]
    for key, value in kwargs.items():
        data_field[f"meta_{key}"] = value
    
    state = template["templates"]
    prompt_text = process_prompt(entrypoint, state)
    prompt_text = postprocess_prompt(prompt_text, template)
    result = {
        "output": unescape_special_characters(prompt_text),
        "seed": seed
    }
    if enhance:
        enhanced_result = enhance_prompt(prompt_text, template)
        result.update(enhanced_result)

    statics = {}
    if "static" in state:
        for key, value in state["static"].items():
            statics[key] = value
    result["statics"] = statics

    return result
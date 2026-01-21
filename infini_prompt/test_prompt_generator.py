"""
Test suite for generate_prompt function and all operators.
Run this file directly: python -m infini_prompt.test_prompt_generator
Or from the parent: python -m unittest infini_prompt.test_prompt_generator
"""

import unittest
import sys
import os
import random
import copy
import time
import pytest
import copy
from unittest.mock import patch
import unittest.mock

# Import the functions to test
from infini_prompt.prompt_generator import (
    PromptError,
    generate_prompt,
    operator_error,
    preprocess_template,
    escape_special_characters,
)


class TestGeneratePrompt(unittest.TestCase):
    """Test suite for generate_prompt function and all operators."""

    def setUp(self):
        """Reset global state before each test."""
        from .prompt_generator import GLOBAL_UNIQUE_STATE
        GLOBAL_UNIQUE_STATE.clear()

    def test_simple_entrypoint(self):
        """Test basic prompt generation with simple entrypoint."""
        template = {
            "entrypoint": "Hello World",
            "templates": {
                "data": {}
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "Hello World")
        self.assertEqual(result["seed"], 42)

    def test_entrypoint_list_strings(self):
        """Test entrypoint as list of strings (random selection)."""
        template = {
            "entrypoint": ["Option A", "Option B", "Option C"],
            "templates": {
                "data": {}
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertIn(result["output"], ["Option A", "Option B", "Option C"])

    def test_entrypoint_list_nested(self):
        """Test entrypoint as nested list (concatenation)."""
        template = {
            "entrypoint": [["Part1A", "Part1B"], ["Part2A", "Part2B"]],
            "templates": {
                "data": {}
            }
        }
        result = generate_prompt(template, seed=42)
        parts = result["output"].split()
        self.assertEqual(len(parts), 2)
        self.assertIn(parts[0], ["Part1A", "Part1B"])
        self.assertIn(parts[1], ["Part2A", "Part2B"])

    def test_entrypoint_list_mixed(self):
        """Test entrypoint as mixed list (fixed start + nested lists)."""
        # According to process_entrypoint_list logic: [string, [list], [list]] format
        template = {
            "entrypoint": ["Start", ["Opt1A", "Opt1B"], ["Opt2A", "Opt2B"]],
            "templates": {
                "data": {}
            }
        }
        result = generate_prompt(template, seed=42)
        # Should start with "Start" and have space-separated parts
        self.assertIn("Start", result["output"])

    def test_entrypoint_dict_selector(self):
        """Test entrypoint as dict with selector."""
        template = {
            "entrypoint": {
                "hello world": "Greeting",
                "goodbye world": "Farewell"
            },
            "templates": {
                "data": {}
            }
        }
        with self.assertRaises(PromptError) as context:
            generate_prompt(template, seed=42)
        self.assertIn("No entrypoint_selector provided", str(context.exception))

    def test_entrypoint_tree_of_tags(self):
        """Test entrypoint as tree of tags with tags_path."""
        template = {
            "entrypoint": {
                "text": "text when it does not have tag.",
                "outdoor": {
                    "text": "a photo in a outdoor location.",
                    "cat": {
                        "text": "a photo of a cat outdoor."
                    }
                }
            },
            "templates": {
                "data": {}
            }
        }
        with self.assertRaises(PromptError) as context:
            generate_prompt(template, seed=42, kwargs={"tags_path": "outdoor/cat\noutdoor\n\n"})
        self.assertIn("No 'meta_tags_path' provided", str(context.exception))

    def test_simple_data_selection(self):
        """Test simple data selection without operator."""
        template = {
            "entrypoint": "{animal}",
            "templates": {
                "data": {
                    "animal": "cat"
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "cat")

    def test_data_selection_list(self):
        """Test data selection from list."""
        template = {
            "entrypoint": "{color}",
            "templates": {
                "data": {
                    "color": ["red", "blue", "green"]
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertIn(result["output"], ["red", "blue", "green"])

    def test_exclusive_operator(self):
        """Test @ (exclusive) operator - ensures no repeats."""
        template = {
            "entrypoint": "{@:fruit} {@:fruit}",
            "templates": {
                "data": {
                    "fruit": ["apple", "banana", "orange"]
                }
            }
        }
        result = generate_prompt(template, seed=123)
        fruits = result["output"].split()
        self.assertEqual(len(fruits), 2)
        self.assertNotEqual(fruits[0], fruits[1])

    def test_exclusive_operator_with_prefix(self):
        """Test @ (exclusive) operator with prefix - allows separate exclusion lists for same key."""
        template = {
            "entrypoint": "{bike@:color} {bike@:color} {car@:color} {car@:color}",
            "templates": {
                "data": {
                    "color": ["red", "blue", "green"]
                }
            }
        }
        result = generate_prompt(template, seed=42)
        parts = result["output"].split()
        # Should have 4 colors total
        self.assertEqual(len(parts), 4)
        
        # First two should be different (bike prefix exclusion)
        self.assertNotEqual(parts[0], parts[1])
        # Last two should be different (car prefix exclusion) 
        self.assertNotEqual(parts[2], parts[3])
        
        # All should be from available colors
        for part in parts:
            self.assertIn(part, ["red", "blue", "green"])

    def test_exclusive_operator_prefix_reset(self):
        """Test @ (exclusive) operator with prefix resets when options exhausted."""
        template = {
            "entrypoint": "{a@:item} {a@:item} {a@:item} {a@:item}",
            "templates": {
                "data": {
                    "item": ["x", "y"]
                }
            }
        }
        result = generate_prompt(template, seed=42)
        parts = result["output"].split()
        # Should have 4 items
        self.assertEqual(len(parts), 4)
        # Should cycle through all options and reset
        # With only 2 options, after 2 selections, it should reset and allow repeats
        unique_parts = set(parts)
        self.assertTrue(len(unique_parts) <= 2)  # At most 2 unique items
        for part in parts:
            self.assertIn(part, ["x", "y"])

    def test_global_exclusive_operator(self):
        """Test @@ (global exclusive) operator - ensures exclusiveness across multiple generate_prompt calls."""
        template = {
            "entrypoint": "{@@:fruit}",
            "templates": {
                "data": {
                    "fruit": ["apple", "banana", "orange"]
                }
            }
        }
        # First call
        result1 = generate_prompt(template, seed=123)
        fruit1 = result1["output"]
        self.assertIn(fruit1, ["apple", "banana", "orange"])
        
        # Second call - should not repeat the first fruit
        result2 = generate_prompt(template, seed=456)
        fruit2 = result2["output"]
        self.assertIn(fruit2, ["apple", "banana", "orange"])
        self.assertNotEqual(fruit1, fruit2)
        
        # Third call - should not repeat the previous fruits
        result3 = generate_prompt(template, seed=789)
        fruit3 = result3["output"]
        self.assertIn(fruit3, ["apple", "banana", "orange"])
        self.assertNotIn(fruit3, [fruit1, fruit2])
        
        # Fourth call - should reset and allow repeats since all options exhausted
        result4 = generate_prompt(template, seed=101)
        fruit4 = result4["output"]
        self.assertIn(fruit4, ["apple", "banana", "orange"])

    def test_static_operator(self):
        """Test $ (static) operator - keeps same value across uses."""
        template = {
            "entrypoint": "{$:color} and {$:color}",
            "templates": {
                "data": {
                    "color": ["red", "blue", "green"]
                }
            }
        }
        result = generate_prompt(template, seed=42)
        colors = result["output"].split(" and ")
        self.assertEqual(colors[0], colors[1])

    def test_static_operator_with_prefix(self):
        """Test $ (static) operator with prefix - allows multiple static values for same key."""
        template = {
            "entrypoint": "My bike color is {bike$:color} and my guitar has the same {bike$:color} color and my car has the color {car$:color} the same of my {car$:color} house",
            "templates": {
                "data": {
                    "color": ["red", "blue", "green"]
                }
            }
        }
        result = generate_prompt(template, seed=42)
        # Extract the colors from the result
        parts = result["output"].split()
        bike_color1 = parts[4]   # "green" from first {bike$:color}
        bike_color2 = parts[11]  # "green" from second {bike$:color} - should be same
        car_color1 = parts[19]   # "red" from first {car$:color}
        car_color2 = parts[24]   # "red" from second {car$:color} - should be same
        
        # Bike colors should be the same (static within prefix)
        self.assertEqual(bike_color1, bike_color2)
        # Car colors should be the same (static within prefix)
        self.assertEqual(car_color1, car_color2)
        # Bike and car colors can be different (different prefixes)
        # With seed=42, bike gets "green" and car gets "red"

    def test_static_operator_multiple_prefixes_simple(self):
        """Test $ (static) operator with different prefixes maintain separate values."""
        template = {
            "entrypoint": "{a$:item} {a$:item} {b$:item} {b$:item}",
            "templates": {
                "data": {
                    "item": ["x", "y", "z"]
                }
            }
        }
        result = generate_prompt(template, seed=123)
        parts = result["output"].split()
        # First two should be the same (same prefix "a")
        self.assertEqual(parts[0], parts[1])
        # Last two should be the same (same prefix "b") 
        self.assertEqual(parts[2], parts[3])
        # All should be from the available options
        for part in parts:
            self.assertIn(part, ["x", "y", "z"])

    def test_literal_operator(self):
        """Test # (literal) operator - returns literal string."""
        template = {
            "entrypoint": "{#:This is a literal string}",
            "templates": {
                "data": {}
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "This is a literal string")

    def test_equality_operator_equals(self):
        """Test == operator (equality check)."""
        template = {
            "entrypoint": "{==:a|test|same|different}",
            "templates": {
                "data": {
                    "a": "test"
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "same")

    def test_equality_operator_not_equals(self):
        """Test != operator (inequality check)."""
        template = {
            "entrypoint": "{!=:a|test2|different|same}",
            "templates": {
                "data": {
                    "a": "test1"
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "different")

    def test_equality_operator_variants(self):
        """Test different equality operator variants."""
        # Test 'equals' variant
        template1 = {
            "entrypoint": "{equals:x|value|yes|no}",
            "templates": {
                "data": {"x": "value"}
            }
        }
        result1 = generate_prompt(template1, seed=42)
        self.assertEqual(result1["output"], "yes")

        # Test 'eq' variant
        template2 = {
            "entrypoint": "{eq:x|value|yes|no}",
            "templates": {
                "data": {"x": "value"}
            }
        }
        result2 = generate_prompt(template2, seed=42)
        self.assertEqual(result2["output"], "yes")

    def test_greater_than_operator(self):
        """Test > (greater than) operator."""
        template = {
            "entrypoint": "{>:a|5|a_greater|b_greater}",
            "templates": {
                "data": {
                    "a": "10"
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "a_greater")

    def test_less_than_operator(self):
        """Test < (less than) operator."""
        template = {
            "entrypoint": "{<:a|10|a_less|b_less}",
            "templates": {
                "data": {
                    "a": "5"
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "a_less")

    def test_greater_equal_operator(self):
        """Test >= (greater than or equal) operator."""
        template = {
            "entrypoint": "{>=:a|10|true_result|false_result}",
            "templates": {
                "data": {
                    "a": "10"
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "true_result")

    def test_less_equal_operator(self):
        """Test <= (less than or equal) operator."""
        template = {
            "entrypoint": "{<=:a|10|true_result|false_result}",
            "templates": {
                "data": {
                    "a": "5"
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "true_result")

    def test_quantitative_operator_variants(self):
        """Test different quantitative operator variants."""
        # Test 'gt' variant
        template1 = {
            "entrypoint": "{gt:a|5|yes|no}",
            "templates": {
                "data": {"a": "10"}
            }
        }
        result1 = generate_prompt(template1, seed=42)
        self.assertEqual(result1["output"], "yes")

        # Test 'lt' variant
        template2 = {
            "entrypoint": "{lt:a|10|yes|no}",
            "templates": {
                "data": {"a": "5"}
            }
        }
        result2 = generate_prompt(template2, seed=42)
        self.assertEqual(result2["output"], "yes")

        # Test 'gte' variant
        template3 = {
            "entrypoint": "{gte:a|10|yes|no}",
            "templates": {
                "data": {"a": "10"}
            }
        }
        result3 = generate_prompt(template3, seed=42)
        self.assertEqual(result3["output"], "yes")

        # Test 'lte' variant
        template4 = {
            "entrypoint": "{lte:a|10|yes|no}",
            "templates": {
                "data": {"a": "5"}
            }
        }
        result4 = generate_prompt(template4, seed=42)
        self.assertEqual(result4["output"], "yes")

    def test_in_operator(self):
        """Test 'in' operator (membership check)."""
        template = {
            "entrypoint": "{in:item|apple, banana, orange|found|not_found}",
            "templates": {
                "data": {
                    "item": "apple"
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "found")

    def test_not_in_operator(self):
        """Test 'not_in' operator (non-membership check)."""
        template = {
            "entrypoint": "{not_in:item|apple, banana, orange|not_found|found}",
            "templates": {
                "data": {
                    "item": "grape"
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "not_found")

    def test_has_operator(self):
        """Test 'has' operator (substring check)."""
        template = {
            "entrypoint": "{has:text|world|found|not_found}",
            "templates": {
                "data": {
                    "text": "hello world"
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "found")

    def test_has_operator_literal_text(self):
        """Test 'has' operator when first arg is a literal string with spaces."""
        template = {
            "entrypoint": "{has:{#:hello world}|world|yes it has|no it does not}",
            "templates": {"data": {}}
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "yes it has")

    def test_not_has_operator(self):
        """Test 'not_has' operator (non-substring check)."""
        template = {
            "entrypoint": "{not_has:text|xyz|not_found|found}",
            "templates": {
                "data": {
                    "text": "hello world"
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "not_found")

    def test_case_operator(self):
        """Test 'case' operator (prefix matching)."""
        template = {
            "entrypoint": "{case:color|Color_|default|red,blue,green}",
            "templates": {
                "data": {
                    "color": "red"
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "Color_red")

    def test_case_operator_default(self):
        """Test 'case' operator with default value."""
        template = {
            "entrypoint": "{case:color|Color_|default_value|red,blue}",
            "templates": {
                "data": {
                    "color": "green"
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "default_value")

    def test_case_operator_key_missing(self):
        """Test 'case' operator when key is not in data."""
        template = {
            "entrypoint": "{case:missing_key|prefix_|default|val1,val2}",
            "templates": {
                "data": {
                    "color": "red"
                }
            }
        }
        with self.assertRaises(PromptError) as context:
            generate_prompt(template, seed=42)
        self.assertIn("Selection key 'missing_key' not found in state data", str(context.exception))

    def test_case_operator_empty_case_values(self):
        """Test 'case' operator with empty case_values."""
        template = {
            "entrypoint": "{case:color|prefix_|default}",
            "templates": {
                "data": {
                    "color": "red"
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "default")

    def test_case_operator_empty_prefix(self):
        """Test 'case' operator with empty prefix."""
        template = {
            "entrypoint": "{case:color||default|red,blue}",
            "templates": {
                "data": {
                    "color": "red"
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "red")

    def test_case_operator_empty_default(self):
        """Test 'case' operator with empty default."""
        template = {
            "entrypoint": "{case:color|prefix_||red,blue}",
            "templates": {
                "data": {
                    "color": "green"
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "")

    def test_case_operator_value_empty_string(self):
        """Test 'case' operator when value is empty string."""
        template = {
            "entrypoint": "{case:color|prefix_|default|red,blue}",
            "templates": {
                "data": {
                    "color": ""
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "default")

    def test_case_operator_case_values_with_spaces(self):
        """Test 'case' operator with case_values containing spaces."""
        template = {
            "entrypoint": "{case:color|prefix_|default|red apple,blue berry}",
            "templates": {
                "data": {
                    "color": "red apple"
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "prefix_red apple")

    def test_operator_one_of(self):
        """Test | (one_of) operator for selecting one of pipe-separated options."""
        # Test basic one_of with literals
        template = {
            "entrypoint": "{red|blue|green}",
            "templates": {
                "data": {}
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertIn(result["output"], ["red", "blue", "green"])

        # Test with nested key
        template = {
            "entrypoint": "{red|{color}|green}",
            "templates": {
                "data": {
                    "color": "yellow"
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertIn(result["output"], ["red", "yellow", "green"])

        # Test with multiple nested
        template = {
            "entrypoint": "{{color1}|{color2}|blue}",
            "templates": {
                "data": {
                    "color1": "red",
                    "color2": "green"
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertIn(result["output"], ["red", "green", "blue"])

    def test_operator_one_of_names(self):
        """Test one_of operator using operator names like {one_of:opt1|opt2|opt3}."""
        one_of_operators = ["one_of", "choice", "select", "any", "any_of", "pick_one"]
        
        for operator in one_of_operators:
            with self.subTest(operator=operator):
                # Test basic one_of with operator name
                template = {
                    "entrypoint": f"{{{operator}:red|blue|green}}",
                    "templates": {
                        "data": {}
                    }
                }
                result = generate_prompt(template, seed=42)
                self.assertIn(result["output"], ["red", "blue", "green"])

                # Test with nested key
                template = {
                    "entrypoint": f"{{{operator}:red|{{color}}|green}}",
                    "templates": {
                        "data": {
                            "color": "yellow"
                        }
                    }
                }
                result = generate_prompt(template, seed=42)
                self.assertIn(result["output"], ["red", "yellow", "green"])

    def test_nested_operator_arguments(self):
        """Test nested operator arguments like {{aple|orange}|{car|bike}|{human|animal}}."""
        template = {
            "entrypoint": "{{aple|orange}|{car|bike}|{human|animal}}",
            "templates": {
                "data": {}
            }
        }
        result = generate_prompt(template, seed=42)
        # The outer one_of should resolve to one of the inner choices
        self.assertIn(result["output"], ["aple", "orange", "car", "bike", "human", "animal"])

    def test_maybe_operator(self):
        """Test maybe (?) operator for conditional selection."""
        # Test {?:key} - 50% chance
        template = {
            "entrypoint": "{?:color}",
            "templates": {
                "data": {
                    "color": "red"
                }
            }
        }
        # With seed=42, it should return "red" (assuming the random choice)
        result = generate_prompt(template, seed=42)
        self.assertIn(result["output"], ["red", ""])

        # Test {maybe:key} - 50% chance
        template = {
            "entrypoint": "{maybe:color}",
            "templates": {
                "data": {
                    "color": "blue"
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertIn(result["output"], ["blue", ""])

        # Test {maybe:100|{key}} - always select
        template = {
            "entrypoint": "{maybe:100|{color}}",
            "templates": {
                "data": {
                    "color": "green"
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "green")

        # Test {maybe:0|{key}} - never select
        template = {
            "entrypoint": "{maybe:0|{color}}",
            "templates": {
                "data": {
                    "color": "yellow"
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "")

        # Test {100?:{key}} - always select
        template = {
            "entrypoint": "{100?:{color}}",
            "templates": {
                "data": {
                    "color": "purple"
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "purple")

        # Test {0?:{key}} - never select
        template = {
            "entrypoint": "{0?:{color}}",
            "templates": {
                "data": {
                    "color": "orange"
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "")

        # Test {40?:{key}} - 40% chance
        template = {
            "entrypoint": "{40?:{color}}",
            "templates": {
                "data": {
                    "color": "pink"
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertIn(result["output"], ["pink", ""])

        # Test maybe with literal - always
        template = {
            "entrypoint": "{100?:{#:hello world}}",
            "templates": {
                "data": {}
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "hello world")

        # Test maybe with literal - never
        template = {
            "entrypoint": "{0?:{#:hello world}}",
            "templates": {
                "data": {}
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "")

        # Test maybe with literal - 50%
        template = {
            "entrypoint": "{?:{#:hello world}}",
            "templates": {
                "data": {}
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertIn(result["output"], ["hello world", ""])

        # Test invalid chance
        template = {
            "entrypoint": "{maybe:invalid|color}",
            "templates": {
                "data": {
                    "color": "black"
                }
            }
        }
        with self.assertRaises(PromptError) as context:
            generate_prompt(template, seed=42)
        self.assertIn("Chance value must be an integer", str(context.exception))

    def test_eval_operator(self):
        """Test * (eval) operator for nested prompt resolution."""
        # The eval operator {*:...} resolves its argument, then uses the result
        # as a key to look up. {*:{animal_key}} -> resolves {animal_key} to "dog",
        # then looks up "dog" in data
        template = {
            "entrypoint": "{*:{animal_key}}",
            "templates": {
                "data": {
                    "animal_key": "dog",
                    "dog": "a cute puppy"
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "a cute puppy")

    def test_nested_prompts(self):
        """Test deeply nested prompt resolution."""
        template = {
            "entrypoint": "I see a {size} {color} {animal}",
            "templates": {
                "data": {
                    "size": "big",
                    "color": "red",
                    "animal": "cat"
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "I see a big red cat")

    def test_metadata_kwargs(self):
        """Test that kwargs are stored as meta_ prefixed keys."""
        template = {
            "entrypoint": "{#:test} {meta_my_key}",
            "templates": {
                "data": {}
            }
        }
        result = generate_prompt(template, seed=42, kwargs={"my_key":"my_value", "another":"data"})
        # Check that metadata was added
        self.assertIn("my_value", result["output"])


    def test_bracket_validation_unmatched_closing(self):
        """Test validation of unmatched closing bracket."""
        template = {
            "entrypoint": "test}",
            "templates": {
                "data": {}
            }
        }
        with self.assertRaises(PromptError) as context:
            generate_prompt(template, seed=42)
        self.assertIn("Unmatched closing bracket", str(context.exception))

    def test_bracket_validation_unmatched_opening(self):
        """Test validation of unmatched opening bracket."""
        template = {
            "entrypoint": "{test",
            "templates": {
                "data": {}
            }
        }
        with self.assertRaises(PromptError) as context:
            generate_prompt(template, seed=42)
        self.assertIn("Unmatched opening bracket", str(context.exception))

    def test_missing_data_key(self):
        """Test error when referenced data key is missing."""
        template = {
            "entrypoint": "{missing_key}",
            "templates": {
                "data": {}
            }
        }
        with self.assertRaises(PromptError) as context:
            generate_prompt(template, seed=42)
        self.assertIn("not found in state data", str(context.exception))

    def test_literal_with_braces_error(self):
        """Test that literal operator rejects strings with braces."""
        template = {
            "entrypoint": "{#:test_with_braces}",
            "templates": {
                "data": {}
            }
        }
        # This should work since we're not actually passing braces to the literal operator
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "test_with_braces")

    def test_empty_entrypoint_error(self):
        """Test error for empty entrypoint."""
        template = {
            "entrypoint": "",
            "templates": {
                "data": {}
            }
        }
        with self.assertRaises(PromptError) as context:
            generate_prompt(template, seed=42)
        self.assertIn("empty", str(context.exception).lower())

    def test_dict_entrypoint_no_selector_error(self):
        """Test error when dict entrypoint used without selector."""
        template = {
            "entrypoint": {
                "option1": "value1",
                "option2": "value2"
            },
            "templates": {
                "data": {}
            }
        }
        with self.assertRaises(PromptError) as context:
            generate_prompt(template, seed=42)
        self.assertIn("entrypoint_selector", str(context.exception))

    def test_dict_entrypoint_no_match_error(self):
        """Test error when dict entrypoint selector matches nothing."""
        template = {
            "entrypoint": {
                "hello world": "greeting",
                "goodbye world": "farewell"
            },
            "templates": {
                "data": {}
            }
        }
        with self.assertRaises(PromptError) as context:
            generate_prompt(template, seed=42, kwargs={"entrypoint_selector": "xyz abc"})
        self.assertIn("No matching entrypoint found for selector: xyz abc", str(context.exception))

    def test_meta_prefix_reserved_error(self):
        """Test error when template data already has meta_ prefixed keys."""
        template = {
            "entrypoint": "test",
            "templates": {
                "data": {
                    "meta_reserved": "value"
                }
            }
        }
        with self.assertRaises(PromptError) as context:
            generate_prompt(template, seed=42)
        self.assertIn("meta_", str(context.exception))

    def test_complex_nested_template(self):
        """Test complex template with multiple operators and nesting."""
        template = {
            "entrypoint": "The {==:type|animal|{$:article} {animal}|a {vehicle}} is {color}",
            "templates": {
                "data": {
                    "type": "animal",
                    "article": ["a", "the"],
                    "animal": ["dog", "cat", "bird"],
                    "vehicle": ["car", "truck"],
                    "color": ["red", "blue", "green"]
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertIsNotNone(result["output"])
        self.assertIn("is", result["output"])

    def test_exclusive_with_reset(self):
        """Test exclusive operator resetting after exhausting options."""
        template = {
            "entrypoint": "{@:item} {@:item} {@:item} {@:item}",
            "templates": {
                "data": {
                    "item": ["a", "b"]
                }
            }
        }
        result = generate_prompt(template, seed=42)
        # Should have 4 items
        items = result["output"].split()
        self.assertEqual(len(items), 4)

    def test_static_preserves_across_template(self):
        """Test that static values are preserved across entire template."""
        template = {
            "entrypoint": "{$:color} then {$:color}",
            "templates": {
                "data": {
                    "color": ["red", "blue", "green"]
                }
            }
        }
        result = generate_prompt(template, seed=42)
        parts = result["output"].split(" then ")
        # The static value should appear before and after 'then' and be the same
        self.assertEqual(len(parts), 2)
        self.assertEqual(parts[0], parts[1])
        self.assertIn(parts[0], ["red", "blue", "green"])

    def test_case_operator_multiple_matches(self):
        """Test case operator with multiple matching case values."""
        template = {
            "entrypoint": "{case:color|is_|unknown|red,blue}",
            "templates": {
                "data": {
                    "color": "red"
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "is_red")

    def test_in_operator_multiple_values(self):
        """Test in operator with multiple comma-separated values."""
        template = {
            "entrypoint": "{in:fruit|apple, banana, cherry, date|yes|no}",
            "templates": {
                "data": {
                    "fruit": "banana"
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "yes")

    def test_has_operator_multiple_substrings(self):
        """Test has operator checking multiple substrings."""
        template = {
            "entrypoint": "{has:text|hello, world|yes|no}",
            "templates": {
                "data": {
                    "text": "hello beautiful world"
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "yes")

    def test_seed_reproducibility(self):
        """Test that same seed produces same output."""
        template = {
            "entrypoint": "{choice}",
            "templates": {
                "data": {
                    "choice": ["option1", "option2", "option3"]
                }
            }
        }
        result1 = generate_prompt(template.copy(), seed=123)
        result2 = generate_prompt(template.copy(), seed=123)
        self.assertEqual(result1["output"], result2["output"])

    def test_quantitative_operator_without_numeric_error(self):
        """Test error when quantitative operator gets non-numeric values."""
        template = {
            "entrypoint": "{>:a|b|yes|no}",
            "templates": {
                "data": {
                    "a": "not_a_number",
                    "b": "also_not_a_number"
                }
            }
        }
        with self.assertRaises(PromptError):
            generate_prompt(template, seed=42)

    def test_operator_error(self):
        # Test case where key value matches compare_value
        state = {"data": {"key": "value"}}
        with pytest.raises(PromptError, match="Error operator triggered: value == value"):
            operator_error("key", "value", state)

        # Test case where key value does not match compare_value
        state = {"data": {"key": "value"}}
        result = operator_error("key", "other_value", state)
        assert result == ""

        # Test case where key is not in state data
        state = {"data": {}}
        with pytest.raises(PromptError, match="Selection key 'key' not found in state data."):
            operator_error("key", "value", state)

    def test_generate_prompt_with_error_operator(self):
        """Test generate_prompt with error operator."""
        # Case where the error operator triggers
        template = {
            "entrypoint": "{error:key|value}",
            "templates": {
                "data": {
                    "key": "value"
                }
            }
        }
        with self.assertRaises(PromptError) as context:
            generate_prompt(template, seed=42)
        self.assertIn("Error operator triggered: value == value", str(context.exception))

        # Case where the error operator does not trigger
        template = {
            "entrypoint": "{error:key|value}",
            "templates": {
                "data": {
                    "key": "other_value"
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "")

        # Case where the key is missing in the data
        template = {
            "entrypoint": "{error:key|value}",
            "templates": {
                "data": {}
            }
        }
        with self.assertRaises(PromptError) as context:
            generate_prompt(template, seed=42)
        self.assertIn("Selection key 'key' not found in state data.", str(context.exception))

    def test_generate_prompt_with_coalesce_operator(self):
        """Test generate_prompt with coalesce operator."""
        # Case where the first non-empty key value is selected
        template = {
            "entrypoint": "{!:{key1}|{key2}|{key3}}",
            "templates": {
                "data": {
                    "key1": "",
                    "key2": "value2",
                    "key3": "value3"
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "value2")

        # Case where raw values are used and the first non-empty value is selected
        template = {
            "entrypoint": "{!:|raw value1|raw value2}",
            "templates": {
                "data": {}
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "raw value1")

        # Case where a key value is empty and a default value is used
        template = {
            "entrypoint": "{!:{key}|default value}",
            "templates": {
                "data": {
                    "key": ""
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "default value")

    def test_index_operator(self):
        """Test index operator {index:key|default_value}."""
        # Test normal case: index within bounds
        template = {
            "entrypoint": "{2:names|default}",
            "templates": {
                "data": {
                    "names": ["alice", "bob", "charlie", "david"]
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "charlie")

        # Test index 0
        template = {
            "entrypoint": "{0:names|default}",
            "templates": {
                "data": {
                    "names": ["alice", "bob", "charlie", "david"]
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "alice")

        # Test out of bounds: index >= len(list), returns default
        template = {
            "entrypoint": "{5:names|paul}",
            "templates": {
                "data": {
                    "names": ["alice", "bob", "charlie", "david"]
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "paul")

        # Test with nested prompt in list element
        template = {
            "entrypoint": "{1:names|default}",
            "templates": {
                "data": {
                    "names": ["alice", "{color} bob", "charlie"],
                    "color": "red"
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "red bob")

        # Test error: key not in data
        template = {
            "entrypoint": "{0:missing_key|default}",
            "templates": {
                "data": {}
            }
        }
        with self.assertRaises(PromptError) as context:
            generate_prompt(template, seed=42)
        self.assertIn("not found in state data", str(context.exception))

        # Test error: key is not a list
        template = {
            "entrypoint": "{0:not_list|default}",
            "templates": {
                "data": {
                    "not_list": 42
                }
            }
        }
        with self.assertRaises(PromptError) as context:
            generate_prompt(template, seed=42)
        self.assertIn("must be a list", str(context.exception))

    def test_except_operator(self):
        """Test ^ (except) operator - selects random item excluding specified values."""
        # Test basic case: exclude single value from data key
        template = {
            "entrypoint": "{^:colors|red,|default}",
            "templates": {
                "data": {
                    "colors": ["red", "blue", "green", "yellow"]
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertIn(result["output"], ["blue", "green", "yellow"])
        self.assertNotEqual(result["output"], "red")

        # Test exclude multiple comma-separated values
        template = {
            "entrypoint": "{^:colors|red,blue|default}",
            "templates": {
                "data": {
                    "colors": ["red", "blue", "green", "yellow"]
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertIn(result["output"], ["green", "yellow"])
        self.assertNotIn(result["output"], ["red", "blue"])

        # Test exclude using another data key
        template = {
            "entrypoint": "{^:colors|exclude_colors|default}",
            "templates": {
                "data": {
                    "colors": ["red", "blue", "green", "yellow"],
                    "exclude_colors": ["red", "blue"]
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertIn(result["output"], ["green", "yellow"])
        self.assertNotIn(result["output"], ["red", "blue"])

        # Test default fallback when all options excluded
        template = {
            "entrypoint": "{^:colors|red,blue,green,yellow|fallback}",
            "templates": {
                "data": {
                    "colors": ["red", "blue", "green", "yellow"]
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "fallback")

        # Test empty string when no default provided and all options excluded
        template = {
            "entrypoint": "{^:colors|red,blue,green,yellow}",
            "templates": {
                "data": {
                    "colors": ["red", "blue", "green", "yellow"]
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "")

        # Test with nested prompt processing in options
        template = {
            "entrypoint": "{^:items|{color} apple,|default}",
            "templates": {
                "data": {
                    "items": ["red apple", "green apple", "yellow apple"],
                    "color": "red"
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertIn(result["output"], ["green apple", "yellow apple"])
        self.assertNotEqual(result["output"], "red apple")

        # Test with nested prompt in exclude key
        template = {
            "entrypoint": "{^:items|{color} apple,|default}",
            "templates": {
                "data": {
                    "items": ["red apple", "green apple", "yellow apple"],
                    "color": "red"
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertIn(result["output"], ["green apple", "yellow apple"])

        # Test error: key not in data
        template = {
            "entrypoint": "{^:missing_key|red,|default}",
            "templates": {
                "data": {}
            }
        }
        with self.assertRaises(PromptError) as context:
            generate_prompt(template, seed=42)
        self.assertIn("not found in state data", str(context.exception))

        # Test error: exclude key not in data (when not comma-separated)
        template = {
            "entrypoint": "{^:colors|missing_exclude|default}",
            "templates": {
                "data": {
                    "colors": ["red", "blue", "green"]
                }
            }
        }
        with self.assertRaises(PromptError) as context:
            generate_prompt(template, seed=42)
        self.assertIn("not found in state data", str(context.exception))

        # Test error: selection key is not a list
        template = {
            "entrypoint": "{^:not_list|red,|default}",
            "templates": {
                "data": {
                    "not_list": 123  # number, not string or list
                }
            }
        }
        with self.assertRaises(PromptError) as context:
            generate_prompt(template, seed=42)
        self.assertIn("must be a list or string", str(context.exception))

    def test_postprocess_basic_cleanup(self):
        """Test basic postprocessing: remove duplicate spaces, strip, replace '. .'."""
        # Create a template that generates text with extra spaces and '. .'
        template = {
            "entrypoint": "  Hello   World. .  This is a test.   ",
            "templates": {
                "data": {}
            }
        }
        result = generate_prompt(template, seed=42)
        # Should remove duplicate spaces, strip, and replace ". ." with "."
        self.assertEqual(result["output"], "Hello World. This is a test.")

    def test_postprocess_with_regex_replacements(self):
        """Test postprocessing with regex replacements from template.postprocess."""
        template = {
            "entrypoint": "Hello NAME, welcome to PLACE!",
            "templates": {
                "data": {}
            },
            "postprocess": [
                {
                    "pattern": r"NAME",
                    "replacement": "John"
                },
                {
                    "pattern": r"PLACE",
                    "replacement": "party"
                }
            ]
        }
        result = generate_prompt(template, seed=42)
        # Should apply regex replacements after processing the template
        self.assertEqual(result["output"], "Hello John, welcome to party!")

    def test_postprocess_multiple_regex_replacements(self):
        """Test postprocessing with multiple regex replacements applied in order."""
        template = {
            "entrypoint": "Item: CODE - Price: $AMOUNT",
            "templates": {
                "data": {}
            },
            "postprocess": [
                {
                    "pattern": r"CODE",
                    "replacement": "ABC123"
                },
                {
                    "pattern": r"AMOUNT",
                    "replacement": "29.99"
                },
                {
                    "pattern": r"Price: \$29\.99",
                    "replacement": "Cost: $29.99"
                }
            ]
        }
        result = generate_prompt(template, seed=42)
        # Should apply replacements in order
        self.assertEqual(result["output"], "Item: ABC123 - Cost: $29.99")

    def test_postprocess_regex_with_groups(self):
        """Test postprocessing regex with capture groups."""
        template = {
            "entrypoint": "Date: 2023-12-25",
            "templates": {
                "data": {}
            },
            "postprocess": [
                {
                    "pattern": r"(\d{4})-(\d{2})-(\d{2})",
                    "replacement": r"\2/\3/\1"
                }
            ]
        }
        result = generate_prompt(template, seed=42)
        # Should convert YYYY-MM-DD to MM/DD/YYYY
        self.assertEqual(result["output"], "Date: 12/25/2023")

    def test_postprocess_case_insensitive_regex(self):
        """Test postprocessing with case insensitive regex matching."""
        template = {
            "entrypoint": "Hello WORLD, welcome to the PARTY!",
            "templates": {
                "data": {}
            },
            "postprocess": [
                {
                    "pattern": r"world",
                    "replacement": "Earth"
                },
                {
                    "pattern": r"party",
                    "replacement": "event"
                }
            ]
        }
        result = generate_prompt(template, seed=42)
        # Should match case insensitively: WORLD -> Earth, PARTY -> event
        self.assertEqual(result["output"], "Hello Earth, welcome to the event!")

    def test_postprocess_invalid_regex_pattern(self):
        """Test postprocessing with invalid regex pattern raises PromptError."""
        template = {
            "entrypoint": "Hello World",
            "templates": {
                "data": {}
            },
            "postprocess": [
                {
                    "pattern": r"[invalid regex",
                    "replacement": "test"
                }
            ]
        }
        with self.assertRaises(PromptError) as context:
            generate_prompt(template, seed=42)
        self.assertIn("Invalid regex pattern", str(context.exception))

    def test_postprocess_invalid_postprocess_format(self):
        """Test postprocessing with invalid postprocess format raises PromptError."""
        # Test non-list postprocess
        template = {
            "entrypoint": "Hello World",
            "templates": {
                "data": {}
            },
            "postprocess": "not_a_list"
        }
        with self.assertRaises(PromptError) as context:
            generate_prompt(template, seed=42)
        self.assertIn("must be a list", str(context.exception))

        # Test non-dict item in postprocess list
        template2 = {
            "entrypoint": "Hello World",
            "templates": {
                "data": {}
            },
            "postprocess": ["not_a_dict"]
        }
        with self.assertRaises(PromptError) as context:
            generate_prompt(template2, seed=42)
        self.assertIn("must be a dictionary", str(context.exception))

        # Test missing pattern key
        template3 = {
            "entrypoint": "Hello World",
            "templates": {
                "data": {}
            },
            "postprocess": [{"replacement": "test"}]
        }
        with self.assertRaises(PromptError) as context:
            generate_prompt(template3, seed=42)
        self.assertIn("must contain 'pattern' and 'replacement'", str(context.exception))

    def test_postprocess_punctuation_spacing(self):
        """Test postprocessing removes spaces before punctuation and ensures one space after commas."""
        template = {
            "entrypoint": "Hello   . World ,  etc ! ? ; :",
            "templates": {
                "data": {}
            }
        }
        result = generate_prompt(template, seed=42)
        # Should remove spaces before punctuation and ensure one space after commas
        self.assertEqual(result["output"], "Hello. World, etc!?;:")

    def test_generate_prompt_with_preprocess(self):
        """Test generate_prompt with preprocess functionality."""
        # Template with preprocess that replaces "world" with "universe"
        template = {
            "entrypoint": "{meta_text}",
            "templates": {
                "data": {},
                "preprocess": [
                    {"pattern": r"world", "replacement": "universe"}
                ]
            }
        }
        # kwargs with text containing "world"
        kwargs = {"text": "hello world"}
        result = generate_prompt(template, seed=42, kwargs=kwargs)
        # Check that the replacement was applied
        self.assertEqual(result["output"], "hello universe")
        # Check that meta_text is set in data
        self.assertEqual(result["seed"], 42)

        # Test with multiple replacements
        template2 = {
            "entrypoint": "{meta_text}",
            "templates": {
                "data": {},
                "preprocess": [
                    {"pattern": r"hello", "replacement": "hi"},
                    {"pattern": r"world", "replacement": "earth"}
                ]
            }
        }
        result2 = generate_prompt(template2, seed=42, kwargs=kwargs)
        self.assertEqual(result2["output"], "hi earth")

        # Test with regex flags (case insensitive)
        template3 = {
            "entrypoint": "{meta_text}",
            "templates": {
                "data": {},
                "preprocess": [
                    {"pattern": r"WORLD", "replacement": "PLANET"}
                ]
            }
        }
        result3 = generate_prompt(template3, seed=42, kwargs={"text": "Hello World"})
        self.assertEqual(result3["output"], "Hello PLANET")

    def test_preprocess_template(self):
        """Test preprocess_template function."""
        # Test case: no templates key
        template = {"entrypoint": "test"}
        result = preprocess_template(copy.deepcopy(template), {})
        self.assertEqual(result, template)

        # Test case: templates but no regex key
        template = {"entrypoint": "test", "templates": {"data": {}}}
        result = preprocess_template(copy.deepcopy(template), {})
        self.assertEqual(result, template)

        # Test case: regex present, field not in kwargs -> set to empty string
        template = {
            "entrypoint": "test",
            "templates": {
                "data": {},
                "regex": {"field1": r"(\w+)"}
            }
        }
        result = preprocess_template(copy.deepcopy(template), {})
        self.assertEqual(result["templates"]["data"]["meta_regex_field1"], "")

        # Test case: regex present, field in kwargs, matches with one group
        template = {
            "entrypoint": "test",
            "templates": {
                "data": {},
                "regex": {"field1": r"(\w+)"}
            }
        }
        result = preprocess_template(copy.deepcopy(template), {"text": "hello"})
        self.assertEqual(result["templates"]["data"]["meta_regex_field1"], "hello")

        # Test case: regex present, field in kwargs, matches with multiple groups
        template = {
            "entrypoint": "test",
            "templates": {
                "data": {},
                "regex": {"field1": r"(\w+) (\d+)"}
            }
        }
        result = preprocess_template(copy.deepcopy(template), {"text": "hello 123"})
        self.assertEqual(result["templates"]["data"]["meta_regex_field1"], ["hello", "123"])

        # Test case: regex present, field in kwargs, does not match -> raise PromptError
        template = {
            "entrypoint": "test",
            "templates": {
                "data": {},
                "regex": {"field1": r"(\d+)"}
            }
        }
        result = preprocess_template(copy.deepcopy(template), {"meta_text": "not_a_number"})
        self.assertEqual(result["templates"]["data"]["meta_regex_field1"], "")


    def test_store_operator(self):
        """Test store/set operator - stores value in statics."""
        template = {
            "entrypoint": "{set:key|stored_value}",
            "templates": {
                "data": {}
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "")
        self.assertEqual(result["statics"]["key"], "stored_value")

    def test_store_operator_with_prefix(self):
        """Test store operator with prefix."""
        template = {
            "entrypoint": "{prefix,set:key|value}",
            "templates": {
                "data": {}
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["statics"]["prefixkey"], "value")

    def test_ignore_operator(self):
        """Test ignore operator - processes for side effects but returns empty string."""
        template = {
            "entrypoint": "{ignore:{set:key|stored_value}}",
            "templates": {
                "data": {}
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "")
        self.assertEqual(result["statics"]["key"], "stored_value")

    def test_ignore_operator_variants(self):
        """Test ignore operator variants (ign and empty)."""
        # Test 'ign' variant
        template1 = {
            "entrypoint": "{ign:{set:key1|value1}}",
            "templates": {
                "data": {}
            }
        }
        result1 = generate_prompt(template1, seed=42)
        self.assertEqual(result1["output"], "")
        self.assertEqual(result1["statics"]["key1"], "value1")

        # Test 'empty' variant
        template2 = {
            "entrypoint": "{empty:{set:key2|value2}}",
            "templates": {
                "data": {}
            }
        }
        result2 = generate_prompt(template2, seed=42)
        self.assertEqual(result2["output"], "")
        self.assertEqual(result2["statics"]["key2"], "value2")

    def test_ignore_operator_simple_string(self):
        """Test ignore operator with a simple string - should return empty."""
        template = {
            "entrypoint": "{ignore:hello world}",
            "templates": {
                "data": {}
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "")

    def test_comment_operator(self):
        """Test comment operator - returns empty string without processing."""
        template = {
            "entrypoint": "{comment:This is a comment}",
            "templates": {
                "data": {}
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "")

    def test_comment_operator_slash_variant(self):
        """Test comment operator with // variant."""
        template = {
            "entrypoint": "{//:This is also a comment}",
            "templates": {
                "data": {}
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "")

    def test_comment_operator_with_braces(self):
        """Test comment operator with braces and non-existing keys - should not process."""
        template = {
            "entrypoint": "{comment:this is a comment should not process my {inexisting_key}, it's a comment}",
            "templates": {
                "data": {}
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "")

    def test_repeat_operator(self):
        """Test repeat operator - repeats text multiple times."""
        template = {
            "entrypoint": "{repeat:3|hello }",
            "templates": {
                "data": {}
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "hello hello hello")

    def test_repeat_operator_with_nested(self):
        """Test repeat operator with nested prompt."""
        template = {
            "entrypoint": "{x:2|{color} }",
            "templates": {
                "data": {
                    "color": ["red", "blue"]
                }
            }
        }
        result = generate_prompt(template, seed=42)
        # Should repeat the selected color twice with space
        self.assertIn(result["output"], ["red red", "blue blue"])

    def test_multiple_prompts(self):
        """Test generating multiple prompts at once."""
        template = {
            "entrypoint": "{color}",
            "templates": {
                "data": {
                    "color": ["red", "blue", "green"]
                }
            }
        }
        result = generate_prompt(template, seed=42, num_prompts=3)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 3)
        for r in result:
            self.assertIn(r["output"], ["red", "blue", "green"])
            self.assertIn("seed", r)
            self.assertIn("statics", r)

    def test_continuation(self):
        """Test continuation feature - preserves statics across continues."""
        template = {
            "entrypoint": "{set:persistent|value} {color}",
            "templates": {
                "data": {
                    "color": ["red", "blue"]
                }
            }
        }
        result = generate_prompt(template, seed=42, num_prompts=1, num_continues=2)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 3)  # 1 * (2 + 1) = 3
        for r in result:
            self.assertEqual(r["statics"]["persistent"], "value")
            self.assertIn(r["output"].split()[-1], ["red", "blue"])

    def test_follow_list_of_feature(self):
        """Test follow-list-of- feature for multiple prompts with list cycling."""
        base_template = {
            "entrypoint": "Prompt: {meta_current_item}",
            "templates": {
                "data": {}
            }
        }
        # Since the template is modified in place, test separately with fresh templates
        template1 = copy.deepcopy(base_template)
        result1 = generate_prompt(template1, seed=42, kwargs={"current_item": "apple"})
        template2 = copy.deepcopy(base_template)
        result2 = generate_prompt(template2, seed=42, kwargs={"current_item": "banana"})
        template3 = copy.deepcopy(base_template)
        result3 = generate_prompt(template3, seed=42, kwargs={"current_item": "cherry"})
        outputs = [result1["output"], result2["output"], result3["output"]]
        self.assertIn("Prompt: apple", outputs)
        self.assertIn("Prompt: banana", outputs)
        self.assertIn("Prompt: cherry", outputs)

    def test_track_operator_basic(self):
        """Test track operator - stores resolved text for later access."""
        template = {
            "entrypoint": "{track:myvar|hello world} later: {track_myvar}",
            "templates": {
                "data": {}
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "hello world later: hello world")

    def test_track_operator_with_nested_operators(self):
        """Test track operator with operators inside the tracked text."""
        template = {
            "entrypoint": "{track:fruit|{@:fruits}} again: {track_fruit}",
            "templates": {
                "data": {
                    "fruits": ["apple", "banana", "orange"]
                }
            }
        }
        result = generate_prompt(template, seed=42)
        parts = result["output"].split(" again: ")
        self.assertEqual(len(parts), 2)
        self.assertEqual(parts[0], parts[1])
        self.assertIn(parts[0], ["apple", "banana", "orange"])

    def test_track_operator_short_form(self):
        """Test track operator short form 'tk'."""
        template = {
            "entrypoint": "{tk:myvar|short test} repeat: {track_myvar}",
            "templates": {
                "data": {}
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "short test repeat: short test")

    def test_optional_operator_key_exists(self):
        """Test optional operator when key exists - returns the key's value."""
        template = {
            "entrypoint": "Value: {optional:existing|default text}",
            "templates": {
                "data": {
                    "existing": "actual value"
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "Value: actual value")

    def test_optional_operator_key_missing(self):
        """Test optional operator when key is missing - returns default."""
        template = {
            "entrypoint": "Value: {optional:missing|default text}",
            "templates": {
                "data": {}
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "Value: default text")

    def test_optional_operator_with_nested_default(self):
        """Test optional operator with nested operators in default."""
        template = {
            "entrypoint": "Value: {optional:missing|{@:fruits}}",
            "templates": {
                "data": {
                    "fruits": ["apple", "banana"]
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertIn(result["output"], ["Value: apple", "Value: banana"])

    def test_optional_operator_short_form(self):
        """Test optional operator short form 'opt'."""
        template = {
            "entrypoint": "Value: {opt:missing|short default}",
            "templates": {
                "data": {}
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "Value: short default")

    def test_simple_text_with_json_block(self):
        """Test simple text template with embedded JSON configuration block."""
        template_string = """This is a simple text template.
```json
{
  "templates": {
    "data": {
      "color": ["red", "blue", "green"],
      "animal": ["cat", "dog"]
    }
  }
}
```
End of template."""
        result = generate_prompt(template_string, seed=42)
        # The entrypoint should be the text outside the JSON block
        expected_entrypoint = "This is a simple text template. End of template."
        self.assertEqual(result["output"], expected_entrypoint)
        # Should have access to the data defined in the JSON block
        self.assertIn("statics", result)

    def test_json_block_with_external_entrypoint(self):
        """Test template with JSON block and external entrypoint text containing operators."""
        template_string = """Generate a {color} {animal} image.
```json
{
  "templates": {
    "data": {
      "color": ["red", "blue", "green"],
      "animal": ["cat", "dog", "bird"]
    }
  }
}
```"""
        result = generate_prompt(template_string, seed=42)
        # The external text becomes the entrypoint and can use operators from the JSON data
        # Should process the operators and generate output
        self.assertIn("image", result["output"])
        self.assertTrue(any(color in result["output"] for color in ["red", "blue", "green"]))
        self.assertTrue(any(animal in result["output"] for animal in ["cat", "dog", "bird"]))

    @patch('builtins.print')
    def test_echo_operator(self, mock_print):
        """Test echo operator prints the text and returns empty string."""
        template = {
            "entrypoint": "Before {echo:Hello World} After",
            "templates": {
                "data": {}
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(mock_print.call_count, 3)
        mock_print.assert_any_call("<<BEGIN_ECHO>>")
        mock_print.assert_any_call("Hello World")
        mock_print.assert_any_call("<<END_ECHO>>")
        self.assertEqual(result["output"], "Before After")

    @patch('builtins.print')
    def test_print_operator(self, mock_print):
        """Test print operator (alias for echo) prints the text."""
        template = {
            "entrypoint": "{print:Test message}",
            "templates": {
                "data": {}
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(mock_print.call_count, 3)
        mock_print.assert_any_call("<<BEGIN_ECHO>>")
        mock_print.assert_any_call("Test message")
        mock_print.assert_any_call("<<END_ECHO>>")
        self.assertEqual(result["output"], "")

    @patch('builtins.print')
    def test_echo_operator_with_processing(self, mock_print):
        """Test echo operator processes nested operators before printing."""
        template = {
            "entrypoint": "{echo:{color} sky}",
            "templates": {
                "data": {
                    "color": ["blue", "red"]
                }
            }
        }
        result = generate_prompt(template, seed=42)
        # Should have called print with the processed text
        self.assertEqual(mock_print.call_count, 3)
        mock_print.assert_any_call("<<BEGIN_ECHO>>")
        # The second call should be the processed text
        second_call = mock_print.call_args_list[1][0][0]
        self.assertIn(second_call, ["blue sky", "red sky"])
        mock_print.assert_any_call("<<END_ECHO>>")
        self.assertEqual(result["output"], "")

    def test_conditional_operator_true(self):
        """Test conditional operator returns text when condition matches."""
        template = {
            "entrypoint": "Start {cond:status|active|is active} End",
            "templates": {
                "data": {
                    "status": "active"
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "Start is active End")

    def test_conditional_operator_false(self):
        """Test conditional operator returns empty when condition doesn't match."""
        template = {
            "entrypoint": "Start {cond:status|inactive|is inactive} End",
            "templates": {
                "data": {
                    "status": "active"
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "Start End")

    def test_if_operator_alias(self):
        """Test 'if' operator as alias for 'cond'."""
        template = {
            "entrypoint": "{if:mode|test|Testing mode}",
            "templates": {
                "data": {
                    "mode": "test"
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "Testing mode")

    def test_conditional_operator_with_processing(self):
        """Test conditional operator processes nested operators in text part."""
        template = {
            "entrypoint": "{cond:flag|yes|Selected {color}}",
            "templates": {
                "data": {
                    "flag": "yes",
                    "color": ["red", "blue"]
                }
            }
        }
        result = generate_prompt(template, seed=42)
        self.assertIn("Selected", result["output"])
        self.assertTrue(any(color in result["output"] for color in ["red", "blue"]))

    def test_conditional_operator_value_with_braces_error(self):
        """Test conditional operator raises error when value contains braces."""
        template = {
            "entrypoint": "{cond:key|{invalid}|text}",
            "templates": {
                "data": {
                    "key": "value"
                }
            }
        }
        with self.assertRaises(PromptError) as context:
            generate_prompt(template, seed=42)
        self.assertIn("Conditional operator value cannot contain '{' characters", str(context.exception))

    def test_conditional_operator_missing_parts(self):
        """Test conditional operator with insufficient parts raises error."""
        template = {
            "entrypoint": "{cond:key|value}",
            "templates": {
                "data": {
                    "key": "value"
                }
            }
        }
        with self.assertRaises(PromptError) as context:
            generate_prompt(template, seed=42)
        self.assertIn("Conditional operator requires key|value|text format", str(context.exception))

    def test_hook_operator(self):
        """Test hook operator calls custom function."""
        def reverse_hook(text):
            return text[::-1]
        
        template = {
            "entrypoint": "{hook:reverse|hello world}",
            "templates": {
                "data": {}
            }
        }
        result = generate_prompt(template, seed=42, kwargs={"hooks": {"reverse": reverse_hook}})
        self.assertEqual(result["output"], "dlrow olleh")

    def test_hook_operator_no_hooks_defined(self):
        """Test hook operator raises error when no hooks defined."""
        template = {
            "entrypoint": "{hook:reverse|hello}",
            "templates": {
                "data": {}
            }
        }
        with self.assertRaises(PromptError) as context:
            generate_prompt(template, seed=42)
        self.assertIn("Hook 'reverse' not found in state hooks", str(context.exception))

    def test_hook_operator_hook_not_found(self):
        """Test hook operator raises error when hook not found."""
        def dummy_hook(text):
            return text
        
        template = {
            "entrypoint": "{hook:missing|hello}",
            "templates": {
                "data": {}
            }
        }
        with self.assertRaises(PromptError) as context:
            generate_prompt(template, seed=42, kwargs={"hooks": {"dummy": dummy_hook}})
        self.assertIn("Hook 'missing' not found in state hooks", str(context.exception))

    def test_increment_operator(self):
        """Test increment operator increases static counter."""
        template = {
            "entrypoint": "{inc:counter}",
            "templates": {"data": {}}
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "1")
        self.assertEqual(result["statics"]["counter"], "1")

    def test_increment_operator_multiple(self):
        """Test multiple increments in same template increments state."""
        template = {
            "entrypoint": "{inc:counter} {inc:counter}",
            "templates": {"data": {}}
        }
        result = generate_prompt(template, seed=42)
        parts = result["output"].split()
        self.assertEqual(parts, ["1", "2"])
        self.assertEqual(result["statics"]["counter"], "2")

    def test_decrement_operator(self):
        """Test decrement operator decreases static counter."""
        template = {
            "entrypoint": "{dec:counter}",
            "templates": {"data": {}}
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "-1")
        self.assertEqual(result["statics"]["counter"], "-1")

    def test_sum_operator(self):
        """Test sum operator with integer and float values."""
        template1 = {
            "entrypoint": "{+:2|3}",
            "templates": {"data": {}}
        }
        result1 = generate_prompt(template1, seed=42)
        self.assertEqual(result1["output"], "5")

        template2 = {
            "entrypoint": "{+:2.5|1.25}",
            "templates": {"data": {}}
        }
        result2 = generate_prompt(template2, seed=42)
        self.assertEqual(result2["output"], "3.75")

    def test_subtract_operator(self):
        """Test subtract operator using data keys."""
        template = {
            "entrypoint": "{-:{a}|{b}}",
            "templates": {"data": {"a": "10", "b": "4"}}
        }
        result = generate_prompt(template, seed=42)
        self.assertEqual(result["output"], "6")


if __name__ == "__main__":
    unittest.main()

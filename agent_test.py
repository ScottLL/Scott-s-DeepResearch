import json
import openai
from typing import Dict, Any
from dotenv import load_dotenv
import os
import re
import time

class ComplianceAndClaimsProcessor:
    def __init__(self, api_key: str):
        """Initialize the processor with OpenAI API key."""
        self.client = openai.OpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        
        # self.client = openai.OpenAI(
        #     api_key=api_key,
        #     base_url="https://api.deepseek.com"
        # )
        
       
        # self.client = openai.OpenAI(
        # api_key=api_key,
        # base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        # )
        
        
        
        # # GPT-4 configuration
        # self.client = openai.OpenAI(
        #     api_key=api_key
        #     )

    def get_optimized_prompt(self, json_schema):
        """
        Returns a streamlined prompt with improved citation handling.
        """

        optimized_prompt = f"""
        ## RESPONSE FORMAT
        Respond with valid JSON only, strictly following this schema:
        {json.dumps(json_schema, indent=2)}

        ## YOUR ROLE
        You are an advanced compliance reviewer analyzing input phrases for legal and marketing risks.

        ## CITATION FORMAT REQUIREMENT
        IMPORTANT: Use numbered citations directly within your text:
        - Every reference to a case, law, or example must include a citation number in square brackets: [1], [2], [3] etc. the citation number have to following the case appearing order. 
        - When referencing a citation in text, use the format: "explanation text [1](URL \"Title, Author/Source, Publication date\")" or "[2](URL \"Case name, Court, Year\") reference case details"
        - Format each citation in markdown style: [n](URL \"Author/Source, Publication date...other related contents\")
        - All citation links should include the URL from the Knowledge base
        - Be consistent with citation numbering throughout your analysis
        - Be extremely careful with quotes around Chinese characters - always ensure proper JSON formatting

        ## ANALYSIS REQUIREMENTS

        1. IDENTIFY ALL PROBLEMATIC PHRASES - Find at least 5-10 distinct issues covering:
        - Consumer Clarity issues (ambiguous or misleading language)
        - Sustainability Claim Validation problems (unsubstantiated or vague claims)
        - Comparative Claim Assessment concerns (unfair or unverifiable comparisons)
        - Cultural Sensitivity Evaluation issues (potentially offensive content)

        2. FOR EACH PROBLEMATIC PHRASE:
        - Specify the exact phrase and its location
        - Link to the relevant region_id from the vision analysis
        - Assess visual presentation impact on interpretation
        - Calculate risk scores (details below)
        - Reference KB cases with EXACT source_urls embedded directly within your text
        - Suggest specific modifications with good case examples
        - Embed all citations directly within your analysis text

        3. SCORING CRITERIA:
        - semantic_evaluation.score (0-100):
            • High severity: 80-100
            • Medium severity: 50-79
            • Low severity: 20-49
            • Minor issues: 0-19

        - retrieval_evaluation.score (0-100):
            • Strong similarity to fail cases: 80-100
            • Moderate similarity to fail cases: 50-79
            • More similarity to win cases: 20-49
            • Strong similarity to win cases: 0-19

        - phrase_illegal_level = (semantic_score * 0.70) + (retrieval_score * 0.30)

        - overall_illegal_level = sum(all phrase_illegal_levels) / number_of_phrases

        4. CASE REFERENCE REQUIREMENTS:
        - ONLY use cases provided in input with their exact source_url
        - Include at least two most relevant cases per problematic phrase
        - Always include complete, unmodified source_urls within your inline citations
        - Extract exact case phrases, outcomes and legal provisions
        - Mark all references as from KB, not external databases
        - Provide minimum 100-word explanations for case relevance
        - Embed all citations directly in text using the markdown format

        5. LEGAL COMPLIANCE CHECK:
        - Include analysis in "legal_compliance_check" top-level key
        - Match legal provisions to input language (US/EU for English, China for Chinese)
        - Follow the exact structure required by the schema
        - All cases must include source_urls from the KB
        - All the legal_provisions have to be the law related in the KB with the reference case but not random law
        - Be extremely careful with quotes around Chinese characters - always double check

        6. VISUAL CONTEXT ASSESSMENT:
        - Identify region_id where problematic phrase appears
        - Evaluate how visual elements impact claim interpretation
        - Consider prominence, color, size, and positioning of claims
        - Include visual context in scoring and recommendations

        7. CONTENT DETAIL REQUIREMENTS:
        - All explanations should be at least 500 characters
        - Include specific recommendations with good case examples
        - Describe how good cases successfully avoid similar issues
        - If input is not in English, output entire analysis in that same language

        8. JSON FORMATTING REQUIREMENTS:
        - Always use double quotes for all JSON property names and string values
        - Be extremely careful with quotes around Chinese or non-English text
        - Double check all JSON formatting before returning your response

        ## CRITICAL LANGUAGE REQUIREMENT
        **IMPORTANT**: If the original phrase is not in English (such as Chinese, Japanese, etc.), your ENTIRE output JSON include the text_analyze and legal_compliance_check MUST be in that same language, NOT in English.
        """

        return optimized_prompt

    def process_input_and_generate_output(self, input_data: Dict[str, Any],
                                          vision_data: Dict[str, Any]) -> Dict:
        """Process the input data and vision analysis in one API call while maintaining output structure."""
        # Detect language of input
        is_chinese = self._is_chinese_text(input_data)
        # print(f"Detected language is {'Chinese' if is_chinese else 'English'}")

        # Choose appropriate schema based on language
        if is_chinese:
            json_schema = self._get_chinese_json_schema()
            # Initialize with Chinese field names
            response = {
                "文本分析": [],
                "道德分析": [],
                "法律合规检查": {}
            }
        else:
            json_schema = self._get_english_json_schema()
            # Initialize with English field names
            response = {
                "text_analyze": [],
                "moral_analyze": [],
                "legal_compliance_check": {}
            }

        try:
            # Single call to process both text analysis and legal compliance at once
            full_prompt = self.get_optimized_prompt(json_schema)

            if is_chinese:
                instruction = "分析文本中的问题短语，并提供法律合规检查。请以中文分析并输出所有内容，确保包含文本分析和法律合规检查字段。"
            else:
                instruction = "Analyze the text for problematic phrases and provide a legal compliance check. Include both text_analyze and legal_compliance_check sections in your response."

            full_result = self._call_llm_api(
                prompt=full_prompt,
                input_data=input_data,
                vision_data=vision_data,
                instruction=instruction
            )

            # Process the full result and add the components to the response
            if is_chinese:
                # Handle Chinese response fields
                if full_result and "文本分析" in full_result:
                    response["文本分析"] = full_result["文本分析"]
                elif full_result and "text_analyze" in full_result:
                    response["文本分析"] = full_result["text_analyze"]

                if full_result and "法律合规检查" in full_result:
                    response["法律合规检查"] = full_result["法律合规检查"]
                elif full_result and "legal_compliance_check" in full_result:
                    response["法律合规检查"] = full_result["legal_compliance_check"]

                # Add moral_analyze if present
                if full_result and "道德分析" in full_result:
                    response["道德分析"] = full_result["道德分析"]
            else:
                # Handle English response fields
                if full_result and "text_analyze" in full_result:
                    response["text_analyze"] = full_result["text_analyze"]

                if full_result and "legal_compliance_check" in full_result:
                    response["legal_compliance_check"] = full_result["legal_compliance_check"]

                # Add moral_analyze if present
                if full_result and "moral_analyze" in full_result:
                    response["moral_analyze"] = full_result["moral_analyze"]

            # Handle potential error cases where we couldn't find expected keys
            if is_chinese and not response["文本分析"] and full_result:
                print("Missing 文本分析 in response, checking for other top-level arrays")
                for key, value in full_result.items():
                    if isinstance(value, list) and value and not response["文本分析"]:
                        print(f"Using content from key: {key}")
                        response["文本分析"] = value
                        break

            return response

        except Exception as e:
            print(f"Error during processing: {e}")
            raise

    def _is_chinese_text(self, input_data: str) -> bool:
        """Detect if the input text contains Chinese characters."""
        import re

        # Look for content between <h2> tags that follows the original phrase header
        # Pattern matches: <h1>original phrase:<h1> <h2>actual text here<h2>
        match = re.search(r'<h1>original phrase:<h1>\s*<h2>(.*?)<h2>', input_data,
                          re.IGNORECASE | re.DOTALL)

        # If that specific pattern doesn't match, try more general approach
        if not match:
            # Look for any content between h2 tags (first occurrence)
            match = re.search(r'<h2>(.*?)<h2>', input_data, re.IGNORECASE | re.DOTALL)

        # As a fallback, try the original pattern
        if not match:
            match = re.search(r'original phrase:\s*(.+?)(?:$|\n)', input_data, re.IGNORECASE)

        if not match:
            return False

        original_phrase = match.group(1).strip()

        # Print for debugging
        # print(f"Extracted phrase: {original_phrase[:100]}...")

        # Check if the original phrase contains Chinese characters
        # Chinese character range: \u4e00-\u9fff
        return bool(re.search(r'[\u4e00-\u9fff]', original_phrase))

    def _get_english_json_schema(self):
        """Return the English JSON schema."""
        return {
            "type": "object",
            "properties": {
                "text_analyze": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "input phrase": {"type": "string"},
                            "problematic_phrases": {
                                "type": "array",
                                "minItems": 3,
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "phrase": {"type": "string"},
                                        "location": {"type": "string"},
                                        "visual_context": {
                                            "type": "object",
                                            "properties": {
                                                "region_id": {"type": "integer"},
                                                "visual_elements": {"type": "array",
                                                                    "items": {"type": "string"}},
                                                "presentation_impact": {"type": "string"}
                                            },
                                            "required": ["region_id", "visual_elements",
                                                         "presentation_impact"]
                                        },
                                        "semantic_evaluation": {
                                            "type": "object",
                                            "properties": {
                                                "errors": {
                                                    "type": "array",
                                                    "items": {
                                                        "type": "object",
                                                        "properties": {
                                                            "error_type": {"type": "string"},
                                                            "severity": {"type": "string"},
                                                            "explanation": {
                                                                "type": "string",
                                                                "minLength": 500
                                                            }
                                                        },
                                                        "required": ["error_type", "severity",
                                                                     "explanation"]
                                                    }
                                                },
                                                "score": {"type": "number"}
                                            },
                                            "required": ["errors", "score"]
                                        },
                                        "retrieval_evaluation": {
                                            "type": "object",
                                            "properties": {
                                                "relevant_cases": {
                                                    "type": "object",
                                                    "description": "Collection of relevant cases with case names as keys",
                                                    "additionalProperties": {
                                                        "type": "object",
                                                        "properties": {
                                                            "case_id": {"type": "string"},
                                                            "case_result_type": {"type": "string",
                                                                                 "description": "Win, Fail, Mixed Result, Pending, etc."},
                                                            "jurisdictional_impact": {
                                                                "type": "array",
                                                                "items": {"type": "string"}
                                                            },
                                                            "case_outcome": {"type": "string"},
                                                            "relevance_score": {"type": "number"},
                                                            "product_involved": {"type": "string"},
                                                            "related_phrase": {"type": "string"},
                                                            "risk_reason_vocabulary": {
                                                                "type": "string"},
                                                            "related_law_item": {"type": "string"},
                                                            "law_item_description": {
                                                                "type": "string"},
                                                            "illegal_explain": {
                                                                "type": "string",
                                                                "description": "Include citations within text using format: \"explanation text [1](URL \"Title, Author/Source, Publication date\")\" or \"[2](URL \"Case name, Court, Year\") reference case details\""
                                                            }
                                                        },
                                                        "required": ["case_result_type",
                                                                     "jurisdictional_impact",
                                                                     "case_outcome",
                                                                     "relevance_score",
                                                                     "product_involved",
                                                                     "related_phrase",
                                                                     "risk_reason_vocabulary",
                                                                     "related_law_item",
                                                                     "law_item_description",
                                                                     "illegal_explain"]
                                                    }
                                                },
                                                "comparative_case_analysis": {
                                                    "type": "string",
                                                    "description": "Analysis of how the cases relate to each other and the problematic phrase. Explain why fail cases are more relevant than win cases, or why pending cases might apply. Include citations to all relevant cases. when Include citations within text, using format: \"explanation text [1](URL \"Title, Author/Source, Publication date\")\" or \"[2](URL \"Case name, Court, Year\") reference case details\"",
                                                    "minLength": 500
                                                },
                                                "legal_pattern_identification": {
                                                    "type": "string",
                                                    "description": "Identify common legal patterns across cases that apply to this situation. Highlight differences between outcomes in similar cases. when include citations within text, using format: \"explanation text [1](URL \"Title, Author/Source, Publication date\")\" or \"[2](URL \"Case name, Court, Year\") reference case details\"",
                                                    "minLength": 300
                                                },
                                                "score": {"type": "number"},
                                                "recommended_modifications": {
                                                    "type": "array",
                                                    "items": {
                                                        "type": "object",
                                                        "properties": {
                                                            "original_text": {"type": "string"},
                                                            "suggested_text": {"type": "string"},
                                                            "location": {"type": "string"},
                                                            "explanation": {
                                                                "type": "string",
                                                                "minLength": 500,
                                                                "description": "Include citations within text using format: \"explanation text [1](URL \"Title, Author/Source, Publication date\")\" or \"[2](URL \"Case name, Court, Year\") reference case details\""
                                                            },
                                                            "good_case_examples": {
                                                                "type": "object",
                                                                "properties": {
                                                                    "campaign_name": {
                                                                        "type": "string"},
                                                                    "example_phrase": {
                                                                        "type": "string"},
                                                                    "source_url": {
                                                                        "type": "string"},
                                                                    "reason_for_success": {
                                                                        "type": "string",
                                                                        "minLength": 500,
                                                                        "description": "Include citations within text using format: \"explanation text [1](URL \"Title, Author/Source, Publication date\")\" or \"[2](URL \"Case name, Court, Year\") reference case details\""
                                                                    }
                                                                },
                                                                "required": ["campaign_name",
                                                                             "example_phrase",
                                                                             "source_url",
                                                                             "reason_for_success"]
                                                            }
                                                        },
                                                        "required": ["original_text",
                                                                     "suggested_text", "location",
                                                                     "explanation",
                                                                     "good_case_examples"]
                                                    }
                                                }
                                            },
                                            "required": ["relevant_cases",
                                                         "comparative_case_analysis",
                                                         "legal_pattern_identification", "score",
                                                         "recommended_modifications"]
                                        },
                                        "phrase_illegal_level": {"type": "number"}
                                    },
                                    "required": ["phrase", "location", "visual_context",
                                                 "semantic_evaluation", "retrieval_evaluation",
                                                 "phrase_illegal_level"]
                                }
                            },
                            "overall_illegal_level": {"type": "number"}
                        },
                        "required": ["input phrase", "problematic_phrases", "overall_illegal_level"]
                    }
                },
                "legal_compliance_check": {
                    "type": "object",
                    "properties": {
                        "product_title": {"type": "string"},
                        "product_core_function_legal_analysis": {
                            "type": "object",
                            "properties": {
                                "patent_technical_features": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                },
                                "performance_parameter_highlights": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                },
                                "special_function_highlights": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                }
                            },
                            "required": ["patent_technical_features",
                                         "performance_parameter_highlights",
                                         "special_function_highlights"]
                        },
                        "risk_of_illegal_action_and_typical_cases": {
                            "type": "object",
                            "properties": {
                                "patent_labeling_illegal_action": {
                                    "type": "object",
                                    "properties": {
                                        "problem": {"type": "string"},
                                        "case": {"type": "string"},
                                        "law": {"type": "string"},
                                        "source_url": {"type": "string"},
                                        "illegal_analysis": {
                                            "type": "string",
                                            "minLength": 300,
                                            "description": "Detailed analysis of why this action is illegal based on the case and law. Include citations within text using format: \"explanation text [1](URL \"Title, Author/Source, Publication date\")\" or \"[2](URL \"Case name, Court, Year\") reference case details\""
                                        }
                                    },
                                    "required": ["problem", "case", "law", "source_url",
                                                 "illegal_analysis"]
                                },
                                "false_advertising_of_performance_data": {
                                    "type": "object",
                                    "properties": {
                                        "problem": {"type": "string"},
                                        "case": {"type": "string"},
                                        "legal_provisions": {"type": "string"},
                                        "source_url": {"type": "string"},
                                        "illegal_analysis": {
                                            "type": "string",
                                            "minLength": 300,
                                            "description": "Detailed analysis of why this action is illegal based on the case and legal provisions. Include citations within text using format: \"explanation text [1](URL \"Title, Author/Source, Publication date\")\" or \"[2](URL \"Case name, Court, Year\") reference case details\""
                                        }
                                    },
                                    "required": ["problem", "case", "legal_provisions",
                                                 "source_url", "illegal_analysis"]
                                },
                                "material_description_defects": {
                                    "type": "object",
                                    "properties": {
                                        "problem": {"type": "string"},
                                        "case": {"type": "string"},
                                        "standard": {"type": "string"},
                                        "source_url": {"type": "string"},
                                        "illegal_analysis": {
                                            "type": "string",
                                            "minLength": 300,
                                            "description": "Detailed analysis of why this action is illegal based on the case and standard. Include citations within text using format: \"explanation text [1](URL \"Title, Author/Source, Publication date\")\" or \"[2](URL \"Case name, Court, Year\") reference case details\""
                                        }
                                    },
                                    "required": ["problem", "case", "standard", "source_url",
                                                 "illegal_analysis"]
                                },
                                "comparative_advertising_violation": {
                                    "type": "object",
                                    "properties": {
                                        "problem": {"type": "string"},
                                        "case": {"type": "string"},
                                        "legal_provisions": {"type": "string"},
                                        "source_url": {"type": "string"},
                                        "illegal_analysis": {
                                            "type": "string",
                                            "minLength": 300,
                                            "description": "Detailed analysis of why this action is illegal based on the case and legal provisions. Include citations within text using format: \"explanation text [1](URL \"Title, Author/Source, Publication date\")\" or \"[2](URL \"Case name, Court, Year\") reference case details\""
                                        }
                                    },
                                    "required": ["problem", "case", "legal_provisions",
                                                 "source_url", "illegal_analysis"]
                                }
                            },
                            "required": ["patent_labeling_illegal_action",
                                         "false_advertising_of_performance_data",
                                         "material_description_defects",
                                         "comparative_advertising_violation"]
                        },
                        "compliance_optimization_plan_and_excellent_cases": {
                            "type": "object",
                            "properties": {
                                "patent_marking_specifications": {
                                    "type": "object",
                                    "properties": {
                                        "original_statement": {"type": "string"},
                                        "optimization_plan": {"type": "string", "minLength": 300},
                                        "effectiveness_analysis": {
                                            "type": "string",
                                            "minLength": 300,
                                            "description": "Analysis of why this optimization is beneficial. Include citations within text using format: \"explanation text [1](URL \"Title, Author/Source, Publication date\")\" or \"[2](URL \"Case name, Court, Year\") reference case details\""
                                        }
                                    },
                                    "required": ["original_statement", "optimization_plan",
                                                 "effectiveness_analysis"]
                                },
                                "performance_data_support": {
                                    "type": "object",
                                    "properties": {
                                        "original_comparison_chart": {"type": "string"},
                                        "optimization_plan": {"type": "string", "minLength": 300},
                                        "effectiveness_analysis": {
                                            "type": "string",
                                            "minLength": 300,
                                            "description": "Analysis of why this optimization is beneficial. Include citations within text using format: \"explanation text [1](URL \"Title, Author/Source, Publication date\")\" or \"[2](URL \"Case name, Court, Year\") reference case details\""
                                        }
                                    },
                                    "required": ["original_comparison_chart", "optimization_plan",
                                                 "effectiveness_analysis"]
                                },
                                "material_description_improvement": {
                                    "type": "object",
                                    "properties": {
                                        "original_parameters": {"type": "string"},
                                        "optimization_plan": {"type": "string", "minLength": 300},
                                        "effectiveness_analysis": {
                                            "type": "string",
                                            "minLength": 300,
                                            "description": "Analysis of why this optimization is beneficial. Include citations within text using format: \"explanation text [1](URL \"Title, Author/Source, Publication date\")\" or \"[2](URL \"Case name, Court, Year\") reference case details\""
                                        }
                                    },
                                    "required": ["original_parameters", "optimization_plan",
                                                 "effectiveness_analysis"]
                                },
                                "comparative_publicity_rectification": {
                                    "type": "object",
                                    "properties": {
                                        "original_description": {"type": "string"},
                                        "optimization_plan": {"type": "string", "minLength": 300},
                                        "effectiveness_analysis": {
                                            "type": "string",
                                            "minLength": 300,
                                            "description": "Analysis of why this optimization is beneficial. Include citations within text using format: \"explanation text [1](URL \"Title, Author/Source, Publication date\")\" or \"[2](URL \"Case name, Court, Year\") reference case details\""
                                        }
                                    },
                                    "required": ["original_description", "optimization_plan",
                                                 "effectiveness_analysis"]
                                },
                                "safety_warning_supplement": {
                                    "type": "object",
                                    "properties": {
                                        "new_content": {"type": "string"},
                                        "effectiveness_analysis": {
                                            "type": "string",
                                            "minLength": 300,
                                            "description": "Analysis of why this supplement is beneficial. Include citations within text using format: \"explanation text [1](URL \"Title, Author/Source, Publication date\")\" or \"[2](URL \"Case name, Court, Year\") reference case details\""
                                        }
                                    },
                                    "required": ["new_content", "effectiveness_analysis"]
                                }
                            },
                            "required": ["patent_marking_specifications",
                                         "performance_data_support",
                                         "material_description_improvement",
                                         "comparative_publicity_rectification",
                                         "safety_warning_supplement"]
                        },
                        "emergency_risk_disposal_suggestions": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "attachment": {
                            "type": "object",
                            "properties": {
                                "list_of_necessary_legal_documents": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                },
                                "related_cases": {"type": "string"}
                            },
                            "required": ["list_of_necessary_legal_documents", "related_cases"]
                        }
                    },
                    "required": [
                        "product_title",
                        "product_core_function_legal_analysis",
                        "risk_of_illegal_action_and_typical_cases",
                        "compliance_optimization_plan_and_excellent_cases",
                        "emergency_risk_disposal_suggestions",
                        "attachment"
                    ]
                }
            },
            "required": ["text_analyze", "legal_compliance_check"]
        }

    def _get_chinese_json_schema(self):
        """Return the Chinese JSON schema."""
        return {
            "type": "object",
            "properties": {
                "文本分析": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "输入短语": {"type": "string"},
                            "问题短语": {
                                "type": "array",
                                "minItems": 3,
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "短语": {"type": "string"},
                                        "位置": {"type": "string"},
                                        "视觉上下文": {
                                            "type": "object",
                                            "properties": {
                                                "区域ID": {"type": "integer"},
                                                "视觉元素": {"type": "array",
                                                             "items": {"type": "string"}},
                                                "呈现影响": {"type": "string"}
                                            },
                                            "required": ["区域ID", "视觉元素", "呈现影响"]
                                        },
                                        "语义评估": {
                                            "type": "object",
                                            "properties": {
                                                "错误": {
                                                    "type": "array",
                                                    "items": {
                                                        "type": "object",
                                                        "properties": {
                                                            "错误类型": {"type": "string"},
                                                            "严重程度": {"type": "string"},
                                                            "解释": {
                                                                "type": "string",
                                                                "minLength": 500
                                                            }
                                                        },
                                                        "required": ["错误类型", "严重程度", "解释"]
                                                    }
                                                },
                                                "分数": {"type": "number"}
                                            },
                                            "required": ["错误", "分数"]
                                        },
                                        "检索评估": {
                                            "type": "object",
                                            "properties": {
                                                "相关案例": {
                                                    "type": "object",
                                                    "description": "包含以案例名称为键的相关案例集合",
                                                    "additionalProperties": {
                                                        "type": "object",
                                                        "properties": {
                                                            "案例结果类型": {"type": "string",
                                                                             "description": "胜诉, 败诉, 混合结果, 待定等"},
                                                            "司法影响": {
                                                                "type": "array",
                                                                "items": {"type": "string"}
                                                            },
                                                            "案例结果": {"type": "string"},
                                                            "相关性评分": {"type": "number"},
                                                            "涉及的产品": {"type": "string"},
                                                            "相关短语": {"type": "string"},
                                                            "风险原因词汇": {"type": "string"},
                                                            "相关法律条款": {"type": "string"},
                                                            "法律条款描述": {"type": "string"},
                                                            "违法解释": {
                                                                "type": "string",
                                                                "description": "Include citations within text using format: \"explanation text [1](URL \"Title, Author/Source, Publication date\")\" or \"[2](URL \"Case name, Court, Year\") reference case details\""
                                                            }
                                                        },
                                                        "required": ["案例结果类型", "司法影响",
                                                                     "案例结果", "相关性评分",
                                                                     "涉及的产品", "相关短语",
                                                                     "风险原因词汇", "相关法律条款",
                                                                     "法律条款描述", "违法解释"]
                                                    }
                                                },
                                                "比较案例分析": {
                                                    "type": "string",
                                                    "description": "Analysis of how the cases relate to each other and the problematic phrase. Explain why fail cases are more relevant than win cases, or why pending cases might apply. Include citations to all relevant cases. when Include citations within text, using format: \"explanation text [1](URL \"Title, Author/Source, Publication date\")\" or \"[2](URL \"Case name, Court, Year\") reference case details\"",
                                                    "minLength": 500
                                                },
                                                "法律模式识别": {
                                                    "type": "string",
                                                    "description": "Identify common legal patterns across cases that apply to this situation. Highlight differences between outcomes in similar cases. when include citations within text, using format: \"explanation text [1](URL \"Title, Author/Source, Publication date\")\" or \"[2](URL \"Case name, Court, Year\") reference case details\"",
                                                    "minLength": 300
                                                },
                                                "分数": {"type": "number"},
                                                "建议修改": {
                                                    "type": "array",
                                                    "items": {
                                                        "type": "object",
                                                        "properties": {
                                                            "原文本": {"type": "string"},
                                                            "建议文本": {"type": "string"},
                                                            "位置": {"type": "string"},
                                                            "解释": {
                                                                "type": "string",
                                                                "minLength": 500,
                                                                "description": "Include citations within text using format: \"explanation text [1](URL \"Title, Author/Source, Publication date\")\" or \"[2](URL \"Case name, Court, Year\") reference case details\""
                                                            },
                                                            "优秀案例示例": {
                                                                "type": "object",
                                                                "properties": {
                                                                    "活动名称": {"type": "string"},
                                                                    "示例短语": {"type": "string"},
                                                                    "来源网址": {"type": "string"},
                                                                    "成功原因": {
                                                                        "type": "string",
                                                                        "minLength": 500,
                                                                        "description": "Include citations within text using format: \"explanation text [1](URL \"Title, Author/Source, Publication date\")\" or \"[2](URL \"Case name, Court, Year\") reference case details\""
                                                                    }
                                                                },
                                                                "required": ["活动名称", "示例短语",
                                                                             "来源网址", "成功原因"]
                                                            }
                                                        },
                                                        "required": ["原文本", "建议文本", "位置",
                                                                     "解释", "优秀案例示例"]
                                                    }
                                                }
                                            },
                                            "required": ["相关案例", "比较案例分析", "法律模式识别",
                                                         "分数", "建议修改"]
                                        },
                                        "短语违法程度": {"type": "number"}
                                    },
                                    "required": ["短语", "位置", "视觉上下文", "语义评估",
                                                 "检索评估", "短语违法程度"]
                                }
                            },
                            "整体违法程度": {"type": "number"}
                        },
                        "required": ["输入短语", "问题短语", "整体违法程度"]
                    }
                },
                "法律合规检查": {
                    "type": "object",
                    "properties": {
                        "产品标题": {"type": "string"},
                        "产品核心功能法律分析": {
                            "type": "object",
                            "properties": {
                                "专利技术特点": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                },
                                "性能参数亮点": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                },
                                "特殊功能亮点": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                }
                            },
                            "required": ["专利技术特点", "性能参数亮点", "特殊功能亮点"]
                        },
                        "违法行为风险及典型案例": {
                            "type": "object",
                            "properties": {
                                "专利标注违法行为": {
                                    "type": "object",
                                    "properties": {
                                        "问题": {"type": "string"},
                                        "案例": {"type": "string"},
                                        "法律": {"type": "string"},
                                        "来源网址": {"type": "string"},
                                        "违法分析": {
                                            "type": "string",
                                            "minLength": 300,
                                            "description": "Detailed analysis of why this action is illegal based on the case and law. Include citations within text using format: \"explanation text [1](URL \"Title, Author/Source, Publication date\")\" or \"[2](URL \"Case name, Court, Year\") reference case details\""
                                        }
                                    },
                                    "required": ["问题", "案例", "法律", "来源网址", "违法分析"]
                                },
                                "性能数据虚假宣传": {
                                    "type": "object",
                                    "properties": {
                                        "问题": {"type": "string"},
                                        "案例": {"type": "string"},
                                        "法律规定": {"type": "string"},
                                        "来源网址": {"type": "string"},
                                        "违法分析": {
                                            "type": "string",
                                            "minLength": 300,
                                            "description": "Detailed analysis of why this action is illegal based on the case and legal provisions. Include citations within text using format: \"explanation text [1](URL \"Title, Author/Source, Publication date\")\" or \"[2](URL \"Case name, Court, Year\") reference case details\""
                                        }
                                    },
                                    "required": ["问题", "案例", "法律规定", "来源网址", "违法分析"]
                                },
                                "材料描述缺陷": {
                                    "type": "object",
                                    "properties": {
                                        "问题": {"type": "string"},
                                        "案例": {"type": "string"},
                                        "标准": {"type": "string"},
                                        "来源网址": {"type": "string"},
                                        "违法分析": {
                                            "type": "string",
                                            "minLength": 300,
                                            "description": "Detailed analysis of why this action is illegal based on the case and standard. Include citations within text using format: \"explanation text [1](URL \"Title, Author/Source, Publication date\")\" or \"[2](URL \"Case name, Court, Year\") reference case details\""
                                        }
                                    },
                                    "required": ["问题", "案例", "标准", "来源网址", "违法分析"]
                                },
                                "比较广告违规": {
                                    "type": "object",
                                    "properties": {
                                        "问题": {"type": "string"},
                                        "案例": {"type": "string"},
                                        "法律规定": {"type": "string"},
                                        "来源网址": {"type": "string"},
                                        "违法分析": {
                                            "type": "string",
                                            "minLength": 300,
                                            "description": "Detailed analysis of why this action is illegal based on the case and legal provisions. Include citations within text using format: \"explanation text [1](URL \"Title, Author/Source, Publication date\")\" or \"[2](URL \"Case name, Court, Year\") reference case details\""
                                        }
                                    },
                                    "required": ["问题", "案例", "法律规定", "来源网址", "违法分析"]
                                }
                            },
                            "required": ["专利标注违法行为", "性能数据虚假宣传", "材料描述缺陷",
                                         "比较广告违规"]
                        },
                        "合规优化方案及优秀案例": {
                            "type": "object",
                            "properties": {
                                "专利标注规范": {
                                    "type": "object",
                                    "properties": {
                                        "原始声明": {"type": "string"},
                                        "优化方案": {"type": "string", "minLength": 300},
                                        "有效性分析": {
                                            "type": "string",
                                            "minLength": 300,
                                            "description": "Analysis of why this optimization is beneficial. Include citations within text using format: \"explanation text [1](URL \"Title, Author/Source, Publication date\")\" or \"[2](URL \"Case name, Court, Year\") reference case details\""
                                        }
                                    },
                                    "required": ["original_statement", "optimization_plan",
                                                 "effectiveness_analysis"]
                                },
                                "性能数据支持": {
                                    "type": "object",
                                    "properties": {
                                        "原始对比图表": {"type": "string"},
                                        "优化方案": {"type": "string", "minLength": 300},
                                        "effectiveness_analysis": {
                                            "type": "string",
                                            "minLength": 300,
                                            "description": "Analysis of why this optimization is beneficial. Include citations within text using format: \"explanation text [1](URL \"Title, Author/Source, Publication date\")\" or \"[2](URL \"Case name, Court, Year\") reference case details\""
                                        }
                                    },
                                    "required": ["original_comparison_chart", "optimization_plan",
                                                 "effectiveness_analysis"]
                                },
                                "材料描述改进": {
                                    "type": "object",
                                    "properties": {
                                        "原始参数": {"type": "string"},
                                        "优化方案": {"type": "string", "minLength": 300},
                                        "有效性分析": {
                                            "type": "string",
                                            "minLength": 300,
                                            "description": "Analysis of why this optimization is beneficial. Include citations within text using format: \"explanation text [1](URL \"Title, Author/Source, Publication date\")\" or \"[2](URL \"Case name, Court, Year\") reference case details\""
                                        }
                                    },
                                    "required": ["original_parameters", "optimization_plan",
                                                 "effectiveness_analysis"]
                                },
                                "比较宣传纠正": {
                                    "type": "object",
                                    "properties": {
                                        "原始描述": {"type": "string"},
                                        "优化方案": {"type": "string", "minLength": 300},
                                        "有效性分析": {
                                            "type": "string",
                                            "minLength": 300,
                                            "description": "Analysis of why this optimization is beneficial. Include citations within text using format: \"explanation text [1](URL \"Title, Author/Source, Publication date\")\" or \"[2](URL \"Case name, Court, Year\") reference case details\""
                                        }
                                    },
                                    "required": ["original_description", "optimization_plan",
                                                 "effectiveness_analysis"]
                                },
                                "安全警告补充": {
                                    "type": "object",
                                    "properties": {
                                        "新增内容": {"type": "string"},
                                        "有效性分析": {
                                            "type": "string",
                                            "minLength": 300,
                                            "description": "Analysis of why this supplement is beneficial. Include citations within text using format: \"explanation text [1](URL \"Title, Author/Source, Publication date\")\" or \"[2](URL \"Case name, Court, Year\") reference case details\""
                                        }
                                    },
                                    "required": ["new_content", "effectiveness_analysis"]
                                }
                            },
                            "required": ["patent_marking_specifications",
                                         "performance_data_support",
                                         "material_description_improvement",
                                         "comparative_publicity_rectification",
                                         "safety_warning_supplement"]
                        },
                        "应急风险处置建议": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "附件": {
                            "type": "object",
                            "properties": {
                                "必要法律文件清单": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                },
                                "相关案例": {"type": "string"}
                            },
                            "required": ["list_of_necessary_legal_documents", "related_cases"]
                        }
                    },
                    "required": [
                        "product_title",
                        "product_core_function_legal_analysis",
                        "risk_of_illegal_action_and_typical_cases",
                        "compliance_optimization_plan_and_excellent_cases",
                        "emergency_risk_disposal_suggestions",
                        "attachment"
                    ]
                }
            },
            "required": ["文本分析", "法律合规检查"]
        }

    def _call_llm_api(self, prompt, input_data, vision_data, instruction):
        """Helper method to make individual LLM API calls."""
        # Create combined input
        combined_input = self._prepare_combined_input(input_data, vision_data)

        try:
            # print(f"API call with instruction: {instruction[:100]}...")

            with self.client.beta.chat.completions.stream(
                    model="qwq-32b",
                    temperature=0,
                    seed=42,
                    messages=[
                        {"role": "system", "content": prompt},
                        {"role": "user",
                         "content": f"{instruction}\n\nHere is the combined input data: {json.dumps(combined_input, ensure_ascii=False)}"}
                    ]
            ) as stream:
                completion = stream.get_final_completion()
                content = completion.choices[0].message.content

                # Clean up the response content
                content = content.replace('```json\n', '').replace('\n```', '').strip()

                # Check if cleaned_content is already a dictionary
                if isinstance(content, dict):
                    result = content
                else:
                    # Try to parse as JSON
                    try:
                        result = json.loads(content)
                        # print(f"Successfully parsed JSON with keys: {list(result.keys())}")
                    except json.JSONDecodeError as e:
                        print(f"JSON parsing error: {e}")
                        # Try a more aggressive approach to fix JSON
                        try:
                            # Remove everything outside the outermost curly braces
                            match = re.search(r'(\{.*\})', content, re.DOTALL)
                            if match:
                                json_only = match.group(1)
                                print(f"Extracted JSON-like content: {json_only[:100]}...")
                                result = json.loads(json_only)
                            else:
                                # Last resort: return a structured error
                                result = {"error": "JSON parsing failed",
                                          "partial_content": content[:500]}
                        except Exception as e2:
                            print(f"Second JSON parsing attempt failed: {e2}")

                            # Determine if response should be in Chinese
                            is_chinese = self._is_chinese_text(
                                input_data) or "文本分析" in content or "视觉上下文" in content

                            # Better fallback - attempt to create minimal valid structure
                            if is_chinese:
                                # Create minimal Chinese structure
                                result = {
                                    "文本分析": [{
                                        "输入短语": input_data[:100] + "...",
                                        "问题短语": [],
                                        "整体违法程度": 0
                                    }]
                                }
                            else:
                                # Create minimal English structure
                                result = {
                                    "text_analyze": [{
                                        "input phrase": input_data[:100] + "...",
                                        "problematic_phrases": [],
                                        "overall_illegal_level": 0
                                    }]
                                }

                            # Add error information
                            result["error"] = "JSON parsing failed"
                            result["partial_content"] = content[:1000]

                return result

        except Exception as e:
            print(f"Error during API call: {e}")
            print(
                f"Raw response content: {content if 'content' in locals() else 'No content received'}")
            return {"error": str(e)}

    def _prepare_combined_input(self, input_data, vision_data):
        """Prepare the combined input data structure."""
        vision_descriptions = []
        if vision_data and "regions" in vision_data:
            for region in vision_data["regions"]:
                if "vision_description" in region:
                    vision_descriptions.append({
                        "region_id": region.get("region_id"),
                        "description": region["vision_description"]
                    })

        return {
            "text_data": input_data,
            "vision_analysis": {
                "total_regions": vision_data.get("total_regions", 0),
                "region_descriptions": vision_descriptions
            }
        }


def ensure_complete_references(output_json):
    """
    Scan the JSON output for citations and ensure they're all included in the references section.

    Args:
        output_json (dict): The JSON output from the LLM

    Returns:
        dict: Updated JSON with complete references
    """
    import re

    # Fix: Update pattern to match the correct citation format [n](URL "Description")
    # The current pattern is looking for [[n]](URL "Description") but the actual format is [n](URL "Description")
    citation_pattern = r'\[(\d+)\]\((https?://[^\s"]+)\s*"([^"]+)"\)'

    # Collect all citations from the output
    all_citations = {}

    def scan_for_citations(obj):
        """Recursively scan object for citations in string values"""
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, str):
                    # Find all citations in the text
                    for match in re.finditer(citation_pattern, value):
                        num, url, desc = match.groups()
                        # Proper format: [1] [Case Name](URL "Description")
                        all_citations[num] = f"[{num}] [{desc}]({url} \"{desc}\")"
                else:
                    scan_for_citations(value)
        elif isinstance(obj, list):
            for item in obj:
                scan_for_citations(item)

    # Scan the entire JSON for citations
    scan_for_citations(output_json)

    # Check if this is a Chinese output based on the keys
    is_chinese = False

    # Check both top-level keys and nested keys for Chinese
    if "法律合规检查" in output_json:
        is_chinese = True
    elif "legal_compliance_check" in output_json:
        if isinstance(output_json["legal_compliance_check"], dict) and "产品标题" in output_json["legal_compliance_check"]:
            is_chinese = True

    # Make sure the references section exists in the right language
    if is_chinese:
        # Chinese output
        if "法律合规检查" in output_json and "附件" in output_json["法律合规检查"]:
            if "参考文献" not in output_json["法律合规检查"]["附件"]:
                output_json["法律合规检查"]["附件"]["参考文献"] = []

            # Clear existing references and create proper ones
            references = []

            # Add all found citations in order
            for num in sorted(all_citations.keys(), key=int):
                references.append(all_citations[num])

            output_json["法律合规检查"]["附件"]["参考文献"] = references
        # Additional debug check
        elif "法律合规检查" in output_json:
            print("Found 法律合规检查 but missing 附件 section or it has wrong structure")
            if isinstance(output_json["法律合规检查"], dict):
                print(f"Keys in 法律合规检查: {list(output_json['法律合规检查'].keys())}")
                # Create 附件 if it doesn't exist
                if "附件" not in output_json["法律合规检查"]:
                    output_json["法律合规检查"]["附件"] = {"参考文献": []}
                    
                # Add references
                references = []
                for num in sorted(all_citations.keys(), key=int):
                    references.append(all_citations[num])
                output_json["法律合规检查"]["附件"]["参考文献"] = references
    else:
        # English output
        if "legal_compliance_check" in output_json and "attachment" in output_json[
            "legal_compliance_check"]:
            if "references" not in output_json["legal_compliance_check"]["attachment"]:
                output_json["legal_compliance_check"]["attachment"]["references"] = []

            # Clear existing references and create proper ones
            references = []

            # Add all found citations in order
            for num in sorted(all_citations.keys(), key=int):
                references.append(all_citations[num])

            output_json["legal_compliance_check"]["attachment"]["references"] = references

    return output_json

def main():
    # Load API key from .env file
    load_dotenv()
    api_key = os.getenv("DASHSCOPE_API_KEY")
    # api_key = os.getenv("OPENAI_API_KEY")
    # api_key = os.getenv('DEEPSEEK_API_KEY')
    

    if not api_key:
        print("API key not found in environment variables.")
        return

    processor = ComplianceAndClaimsProcessor(api_key)

    # Load the vision analysis results
    try:
        with open('vision_analysis_results.json', 'r', encoding='utf-8') as f:
            vision_data = json.load(f)
    except Exception as e:
        print(f"Error loading vision analysis results: {e}")
        vision_data = {}

    # Load the advertising cases from file
    try:
        with open('ads_cases.txt', 'r', encoding='utf-8') as f:
            ads_cases = f.read()
    except Exception as e:
        print(f"Error loading advertising cases: {e}")
        ads_cases = ""

    try:
        structured_output = processor.process_input_and_generate_output(ads_cases, vision_data)
        
        # Fix missing references in the output
        structured_output = ensure_complete_references(structured_output)
        
        print("Structured JSON Output:")
        print(json.dumps(structured_output, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
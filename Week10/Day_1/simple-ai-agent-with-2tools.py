"""
Simple AI Agent with Calculator and Web Search
The LLM decides which tool to use based on the user's query
"""

import os
from dotenv import load_dotenv
from openai import OpenAI
from tavily import TavilyClient
import json

# Load environment variables
load_dotenv()

# Initialize clients
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))


def calculator(expression):
    """
    Simple calculator that evaluates mathematical expressions
    """
    try:
        # Safe evaluation of math expression
        result = eval(expression, {"__builtins__": {}}, {})
        return f"Result: {result}"
    except Exception as e:
        return f"Error calculating: {str(e)}"


def web_search(query):
    """
    Search the web using Tavily
    """
    try:
        response = tavily_client.search(query=query, max_results=3)
        
        # Format the results
        results = []
        for result in response.get('results', []):
            results.append(f"Title: {result['title']}\nContent: {result['content']}\nURL: {result['url']}\n")
        
        return "\n".join(results) if results else "No results found"
    except Exception as e:
        return f"Error searching: {str(e)}"


# Define available tools for the LLM
tools = [
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "Performs mathematical calculations. Use this for any math operations like addition, subtraction, multiplication, division, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "The mathematical expression to evaluate (e.g., '25 * 4', '(15 + 7) * 3')"
                    }
                },
                "required": ["expression"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Searches the web for current information, news, facts, or any information not in your knowledge base.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query"
                    }
                },
                "required": ["query"]
            }
        }
    }
]


def run_agent(user_query):
    """
    Main agent function that processes user queries
    """
    print(f"\nUser Query: {user_query}")
    print("=" * 60)
    
    messages = [{"role": "user", "content": user_query}]
    
    # Send query to LLM with available tools
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        tools=tools,
        tool_choice="auto"  # Let the model decide which tool to use
    )
    
    response_message = response.choices[0].message
    
    # Check if the LLM wants to call a tool
    if response_message.tool_calls:
        # Add the assistant's response to messages
        messages.append(response_message)
        
        # Process each tool call
        for tool_call in response_message.tool_calls:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
            
            print(f"\nLLM decided to use: {function_name}")
            print(f"Arguments: {function_args}")
            
            # Call the appropriate function
            if function_name == "calculator":
                function_response = calculator(function_args["expression"])
            elif function_name == "web_search":
                function_response = web_search(function_args["query"])
            else:
                function_response = "Unknown function"
            
            print(f"\nTool Response:\n{function_response}")
            
            # Add the function response to messages
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": function_name,
                "content": function_response
            })
        
        # Get final response from LLM with the tool results
        final_response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages
        )
        
        final_answer = final_response.choices[0].message.content
        print(f"\nFinal Answer:\n{final_answer}")
        print("=" * 60)
        
        return final_answer
    
    else:
        # No tool needed, just return the response
        answer = response_message.content
        print(f"\nAnswer (no tool needed):\n{answer}")
        print("=" * 60)
        return answer


if __name__ == "__main__":
    # Example queries
    
    # Math query - should use calculator
    run_agent("What is 156 multiplied by 23?")
    
    # Web search query - should use web_search
    run_agent("What are the latest developments in AI this week?")
    
    # Another math query
    #run_agent("Calculate (100 + 50) / 3")
    
    # Current events - should use web_search
    #run_agent("Who won the latest NBA game?")

    run_agent("What is the capital of France?")

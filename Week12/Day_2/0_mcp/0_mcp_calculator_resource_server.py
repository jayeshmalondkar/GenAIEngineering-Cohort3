# calculator_server_with_resources.py
from fastmcp import FastMCP
import asyncio
from datetime import datetime
from typing import List, Dict, Any
import json

# Create server instance
mcp = FastMCP("Calculator Server with History")

# State management - calculation history
calculation_history: List[Dict[str, Any]] = []
statistics = {
    "total_calculations": 0,
    "last_result": None,
    "last_operation": None,
    "session_start": datetime.now().isoformat()
}

# Helper function to save calculation
def save_calculation(operation: str, a: float, b: float, result: float):
    """Save calculation to history and update statistics"""
    calculation = {
        "id": len(calculation_history) + 1,
        "timestamp": datetime.now().isoformat(),
        "operation": operation,
        "a": a,
        "b": b,
        "result": result
    }
    calculation_history.append(calculation)

    # Update statistics
    statistics["total_calculations"] += 1
    statistics["last_result"] = result
    statistics["last_operation"] = operation

@mcp.tool()
def add(a: float, b: float) -> float:
    """Add two numbers together and save to history"""
    result = a + b
    save_calculation("add", a, b, result)
    return result

@mcp.tool()
def subtract(a: float, b: float) -> float:
    """Subtract b from a and save to history"""
    result = a - b
    save_calculation("subtract", a, b, result)
    return result

@mcp.tool()
def multiply(a: float, b: float) -> float:
    """Multiply two numbers and save to history"""
    result = a * b
    save_calculation("multiply", a, b, result)
    return result

@mcp.tool()
def divide(a: float, b: float) -> float:
    """Divide a by b and save to history"""
    if b == 0:
        raise ValueError("Cannot divide by zero")
    result = a / b
    save_calculation("divide", a, b, result)
    return result

@mcp.tool()
def clear_history() -> str:
    """Clear the calculation history"""
    global calculation_history
    calculation_history.clear()
    statistics["total_calculations"] = 0
    statistics["last_result"] = None
    statistics["last_operation"] = None
    return "History cleared successfully"

@mcp.tool()
def get_last_result() -> float:
    """Get the last calculation result"""
    if statistics["last_result"] is None:
        raise ValueError("No calculations performed yet")
    return statistics["last_result"]

# Resources for accessing state
@mcp.resource("calculation://history")
async def get_calculation_history() -> str:
    """Get the complete calculation history as JSON"""
    return json.dumps({
        "history": calculation_history,
        "count": len(calculation_history)
    }, indent=2)

@mcp.resource("calculation://statistics")
async def get_statistics() -> str:
    """Get calculation statistics"""
    return json.dumps(statistics, indent=2)

@mcp.resource("calculation://history/{calculation_id}")
async def get_calculation_by_id(calculation_id: str) -> str:
    """Get a specific calculation by ID"""
    try:
        calc_id = int(calculation_id)
        for calc in calculation_history:
            if calc["id"] == calc_id:
                return json.dumps(calc, indent=2)
        raise ValueError(f"Calculation with ID {calc_id} not found")
    except ValueError as e:
        return json.dumps({"error": str(e)})

@mcp.resource("calculation://summary")
async def get_summary() -> str:
    """Get a summary of all calculations"""
    if not calculation_history:
        return json.dumps({"message": "No calculations performed yet"})

    # Calculate summary statistics
    all_results = [calc["result"] for calc in calculation_history]
    operations_count = {}

    for calc in calculation_history:
        op = calc["operation"]
        operations_count[op] = operations_count.get(op, 0) + 1

    summary = {
        "total_calculations": len(calculation_history),
        "operations_breakdown": operations_count,
        "results": {
            "min": min(all_results),
            "max": max(all_results),
            "average": sum(all_results) / len(all_results),
            "last_5_results": [calc["result"] for calc in calculation_history[-5:]]
        },
        "session_info": {
            "start_time": statistics["session_start"],
            "current_time": datetime.now().isoformat()
        }
    }

    return json.dumps(summary, indent=2)

if __name__ == "__main__":
    # Run the server on SSE transport
    print("Starting Calculator Server with Resources on port 9321...")
    print("Available resources:")
    print("  - calculation://history")
    print("  - calculation://statistics")
    print("  - calculation://history/{id}")
    print("  - calculation://summary")
    asyncio.run(mcp.run(transport="sse", port=9321))
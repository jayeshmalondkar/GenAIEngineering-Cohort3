"""
MainWorkflow
Primary workflow for the product
Steps: input, process, output
"""

import logging
from .DataProcessingAgent import DataProcessingAgent

class MainWorkflow:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.agent = DataProcessingAgent()

    def execute(self, input_data):
        self.logger.info("Workflow execution started.")

        # Step 1: Input data validation
        if not self.agent.data_validation(input_data):
            self.logger.error("Data validation failed.")
            return

        # Step 2: Data processing
        processed_data = self.agent.processing(input_data)
        if processed_data is None:
            self.logger.error("Data processing failed.")
            return

        # Step 3: Output result
        analysis_result = self.agent.analysis(processed_data)

        self.logger.info(f"Workflow completed with result: {analysis_result}")
        return analysis_result
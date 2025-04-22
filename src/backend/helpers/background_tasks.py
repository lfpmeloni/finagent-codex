# helpers/background_tasks.py

import asyncio
import logging
from helpers.utils import initialize_runtime_and_context
from context.cosmos_memory import CosmosBufferedChatCompletionContext
from autogen_core import AgentId

async def run_background_tasks():
    while True:
        try:
            logging.info("Background task runner active")
            user_id = "test-user"  # or pull dynamically if needed

            cosmos = CosmosBufferedChatCompletionContext("", user_id)
            plans = await cosmos.get_all_plans()

            for plan in plans:
                steps = await cosmos.get_steps_by_plan(plan.id)
                for step in steps:
                    if step.status == "approved":  # or "planned"
                        logging.info(f"Executing step: {step.action} by {step.agent}")

                        runtime, _ = await initialize_runtime_and_context(plan.session_id, user_id)
                        agent_id = AgentId(step.agent.lower(), plan.session_id)

                        await runtime.send_message(step, agent_id)

                        step.status = "completed"
                        await cosmos.update_step(step)

            await asyncio.sleep(10)

        except Exception as e:
            logging.error(f"Background task crashed: {e}")
            await asyncio.sleep(30)
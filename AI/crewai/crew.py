import sys
import os

# ============================================================
# THÊM THƯ MỤC HIỆN TẠI VÀO PYTHON PATH
# ============================================================

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)


from crewai import Crew, Process
from agents import jewelry_agent
from tasks import create_recommendation_task


# ============================================================
# CHẠY CREW
# ============================================================

def run_crew(query, context):

    task = create_recommendation_task(
        query,
        context
    )

    crew = Crew(
        agents=[
            jewelry_agent
        ],

        tasks=[
            task
        ],

        process=Process.sequential,

        verbose=True
    )

    result = crew.kickoff()

    return str(result)
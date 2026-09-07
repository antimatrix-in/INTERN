"""ANTI MATRIX Automatic Problem Allocation Service

Implements duration-separated, domain-compatible, college-unique random problem
allocation during employee onboarding and project assignment.
"""

import json
import logging
import random
from datetime import datetime, timedelta
from app.extensions import db
from app.models import (
    Project, ProjectAssignment, Student, Internship, InternshipPlan,
    ProjectWeek, ProjectTask, WeeklyMilestone, WeeklyTask, College, AuditLog
)

logger = logging.getLogger(__name__)


class ProblemAllocationService:
    """Service to manage Problem ID allocation rules and assignments."""

    @staticmethod
    def get_eligible_problems(college_id, duration_months, domain=None, exclude_student_id=None):
        """
        Query eligible problems for a specific college and duration.
        Enforces:
          1. Duration pool (1 Month vs 3 Months).
          2. Active project status (is_active == True).
          3. Domain matching/filtering (if domain provided).
          4. Same-college uniqueness (exclude problems with active assignments in this college).
        """
        # 1. Base query on duration and active status
        query = Project.query.filter(
            Project.duration_months == int(duration_months),
            Project.is_active == True
        )

        all_duration_projects = query.all()
        if not all_duration_projects:
            return []

        # 2. Domain matching if domain is provided
        domain_projects = all_duration_projects
        if domain:
            dom_clean = domain.strip().lower()
            matching_domain_projects = [
                p for p in all_duration_projects
                if dom_clean in p.domain.lower() or p.domain.lower() in dom_clean or
                any(keyword in p.domain.lower() for keyword in dom_clean.split() if len(keyword) > 2)
            ]
            if matching_domain_projects:
                domain_projects = matching_domain_projects

        # 3. Same-College Active Assignment Exclusion
        active_statuses = ['ASSIGNED', 'IN_PROGRESS', 'SUBMITTED', 'REVISION_REQUIRED', 'UNDER_EVALUATION', 'ACTIVE']

        conflict_query = db.session.query(ProjectAssignment.project_id)\
            .join(Internship, ProjectAssignment.internship_id == Internship.id)\
            .join(Student, Internship.student_id == Student.id)\
            .filter(
                Student.college_id == college_id,
                Internship.status == 'ACTIVE',
                ProjectAssignment.status.in_(active_statuses)
            )

        if exclude_student_id:
            conflict_query = conflict_query.filter(Student.id != exclude_student_id)

        assigned_project_ids = {row[0] for row in conflict_query.all()}

        # 4. Exclude actively assigned projects
        eligible = [p for p in domain_projects if p.id not in assigned_project_ids]
        return eligible

    @staticmethod
    def allocate_random_problem(college_id, duration_months, domain=None, exclude_student_id=None):
        """
        Randomly select one eligible problem from the pool for the given college and duration.
        Returns (project: Project or None, error_message: str or None).
        """
        college = College.query.get(college_id)
        college_name = college.name if college else "this college"

        eligible = ProblemAllocationService.get_eligible_problems(
            college_id=college_id,
            duration_months=duration_months,
            domain=domain,
            exclude_student_id=exclude_student_id
        )

        if not eligible:
            dur_str = f"{duration_months} Month{'s' if duration_months > 1 else ''}"
            domain_info = f" in domain '{domain}'" if domain else ""
            return None, f"No available {dur_str} problems{domain_info} for {college_name}. Please add another {dur_str} problem before creating or assigning this employee."

        selected = random.choice(eligible)
        return selected, None

    @staticmethod
    def assign_problem_to_internship(internship, project, assigned_by_user=None, deadline=None):
        """
        Assign a project/problem to an internship, initializing the weekly milestone roadmap.
        Generates 4 milestones for 1-Month or 12 milestones for 3-Months.
        Week 1 is AVAILABLE with 7-day initial deadline; subsequent weeks are LOCKED.
        """
        # Calculate deadline if not provided
        if not deadline:
            duration_weeks = project.total_weeks
            start_dt = datetime.utcnow()
            due_dt = start_dt + timedelta(weeks=duration_weeks)
            deadline = due_dt.strftime('%d %b %Y')

        # Create assignment record
        assignment = ProjectAssignment(
            internship_id=internship.id,
            project_id=project.id,
            assigned_by=assigned_by_user.id if assigned_by_user else 1,
            assigned_at=datetime.utcnow(),
            deadline=deadline,
            status='ASSIGNED',
            description=f'Assigned Problem {project.project_code}: {project.title}'
        )
        db.session.add(assignment)
        db.session.flush()

        # Generate weekly milestones from project template weeks
        template_weeks = project.project_weeks.order_by(ProjectWeek.week_number.asc()).all()
        now = datetime.utcnow()
        week_1_due = now + timedelta(days=7)

        # If project has no template weeks defined, create defaults
        if not template_weeks:
            for w_num in range(1, project.total_weeks + 1):
                pw = ProjectWeek(
                    project_id=project.id,
                    week_number=w_num,
                    title=f"Week {w_num} Milestone",
                    description=f"Deliverables for week {w_num}",
                    objective=project.expected_outcome or f"Week {w_num} objectives",
                    instructions=f"Follow the {project.total_weeks}-week roadmap.",
                    deliverables_json=json.dumps([])
                )
                db.session.add(pw)
                db.session.flush()

                pt = ProjectTask(
                    week_id=pw.id,
                    title=f"Execute Week {w_num} core tasks for {project.title}",
                    priority="Medium",
                    estimated_hours=8.0,
                    order_num=1
                )
                db.session.add(pt)
            db.session.flush()
            template_weeks = project.project_weeks.order_by(ProjectWeek.week_number.asc()).all()

        for pw in template_weeks:
            is_first_week = (pw.week_number == 1)
            milestone = WeeklyMilestone(
                assignment_id=assignment.id,
                week_number=pw.week_number,
                title=pw.title,
                objective=pw.objective or pw.description or f"Week {pw.week_number} milestone for {project.title}",
                instructions=pw.instructions,
                deliverables_json=pw.deliverables_json,
                status='AVAILABLE' if is_first_week else 'LOCKED',
                started_at=now if is_first_week else None,
                unlocked_at=now if is_first_week else None,
                due_at=week_1_due if is_first_week else None
            )
            db.session.add(milestone)
            db.session.flush()

            # Copy template tasks into weekly tasks in exact order
            for pt in pw.tasks.order_by(ProjectTask.order_num.asc(), ProjectTask.id.asc()).all():
                wt = WeeklyTask(
                    milestone_id=milestone.id,
                    task_text=pt.title,
                    is_completed=False,
                    order_num=pt.order_num
                )
                db.session.add(wt)

        # Update internship stage
        internship.current_stage = f"Week 1 ({template_weeks[0].title if template_weeks else 'Available'})"
        return assignment

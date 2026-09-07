"""ANTI MATRIX Task Plan JSON Import & Validation Service

Handles parsing, validating, normalising, and atomically importing 1-Month (4 Weeks)
and 3-Month (4 Phases -> 12 Weeks) task plans into the PostgreSQL Supabase database.
"""

import json
import logging
import re
from datetime import datetime
from app.extensions import db
from app.models import Project, ProjectWeek, ProjectTask, TaskImportHistory, User

logger = logging.getLogger(__name__)


class TaskImportService:
    """Service to validate and atomically import internship task plans."""

    @staticmethod
    def normalize_duration(duration_val):
        """Normalize duration input to integer (1 or 3) and canonical string ('1 Month' or '3 Months')."""
        if not duration_val:
            return 1, "1 Month"
        d_str = str(duration_val).strip().lower()
        if "3" in d_str:
            return 3, "3 Months"
        return 1, "1 Month"

    @staticmethod
    def generate_next_problem_id(duration_months):
        """Generate next sequential Problem ID (P1M-001 or P3M-001)."""
        prefix = "P1M" if duration_months == 1 else "P3M"
        existing = Project.query.filter(Project.project_code.like(f"{prefix}-%")).all()
        max_seq = 0
        for p in existing:
            try:
                parts = p.project_code.split("-")
                if len(parts) >= 2 and parts[-1].isdigit():
                    seq = int(parts[-1])
                    if seq > max_seq:
                        max_seq = seq
            except Exception:
                pass
        return f"{prefix}-{max_seq + 1:03d}"

    @staticmethod
    def validate_and_parse(json_content, selected_duration, filename="task_plan.json"):
        """
        Validate and parse the uploaded JSON task plan.
        Returns (is_valid: bool, error_message: str or None, preview_data: dict or None, parsed_payload: dict or None).
        """
        # 1. Parse JSON
        if isinstance(json_content, str):
            try:
                data = json.loads(json_content)
            except json.JSONDecodeError as e:
                return False, f"Invalid JSON file. Please upload a valid task plan. ({str(e)})", None, None
        elif isinstance(json_content, dict):
            data = json_content
        else:
            return False, "Invalid JSON file. Please upload a valid task plan.", None, None

        if not isinstance(data, dict):
            return False, "Invalid JSON root structure. Expected a JSON object.", None, None

        # 2. Check root 'internship' object
        internship = data.get("internship")
        if not internship or not isinstance(internship, dict):
            return False, "Invalid task plan structure: missing root 'internship' object.", None, None

        # 3. Project Title & Domain
        project_title = (internship.get("project_title") or internship.get("title") or "").strip()
        if not project_title:
            return False, "Project title is required in the task plan.", None, None

        domain = (internship.get("domain") or internship.get("category") or "General").strip()
        if not domain:
            domain = "General"

        # 4. Duration validation
        json_duration_raw = internship.get("duration", "")
        if not json_duration_raw:
            return False, "Internship duration is required in the task plan.", None, None

        json_dur_months, json_dur_str = TaskImportService.normalize_duration(json_duration_raw)
        sel_dur_months, sel_dur_str = TaskImportService.normalize_duration(selected_duration)

        if json_dur_months != sel_dur_months:
            return False, f"Selected duration ({sel_dur_str}) does not match the uploaded task plan ({json_duration_raw}).", None, None

        # 5. Problem ID extraction or generation
        raw_problem_id = (
            internship.get("problem_id") or
            internship.get("project_id") or
            internship.get("project_code") or
            internship.get("code") or ""
        ).strip()

        if raw_problem_id:
            problem_id = raw_problem_id.upper()
        else:
            problem_id = TaskImportService.generate_next_problem_id(json_dur_months)

        # 6. Milestone validation
        milestones = internship.get("milestones")
        if not milestones or not isinstance(milestones, list):
            return False, "Milestone data is required and must be an array.", None, None

        total_weeks = 4 if json_dur_months == 1 else 12
        normalized_weeks = []
        total_tasks_count = 0

        if json_dur_months == 1:
            # 1 Month track: expect 4 weekly milestones
            if len(milestones) < 4:
                return False, f"1 Month task plan must contain 4 weekly milestones. Found {len(milestones)}.", None, None

            for i in range(1, 5):
                m_data = milestones[i - 1] if i - 1 < len(milestones) else {}
                if not isinstance(m_data, dict):
                    m_data = {}

                w_title = (m_data.get("title") or f"Week {i} Milestone").strip()
                w_goal = (m_data.get("goal") or "").strip()
                w_completion = str(m_data.get("completion") or f"{i * 25}%").strip()
                w_github = (m_data.get("github_requirement") or "").strip()
                w_condition = (m_data.get("completion_condition") or "").strip()
                w_demo = m_data.get("demo_output") or {}
                w_expected = m_data.get("expected_features") or []

                raw_tasks = m_data.get("tasks", [])
                if not isinstance(raw_tasks, list):
                    raw_tasks = [str(raw_tasks)] if raw_tasks else []

                tasks_list = []
                for t_idx, t_item in enumerate(raw_tasks, 1):
                    if isinstance(t_item, dict):
                        t_title = t_item.get("title") or t_item.get("task") or str(t_item)
                        t_desc = t_item.get("description") or ""
                    else:
                        t_title = str(t_item).strip()
                        t_desc = ""

                    if t_title:
                        tasks_list.append({
                            "order_num": t_idx,
                            "title": t_title,
                            "description": t_desc,
                            "priority": "Medium",
                            "estimated_hours": 8.0
                        })

                total_tasks_count += len(tasks_list)
                normalized_weeks.append({
                    "week_number": i,
                    "title": w_title,
                    "phase_number": None,
                    "phase_title": None,
                    "weeks_label": None,
                    "completion_percentage": w_completion,
                    "goal": w_goal,
                    "objective": w_goal,
                    "instructions": f"Complete all Week {i} deliverables for {project_title}.",
                    "github_requirement": w_github,
                    "completion_condition": w_condition,
                    "demo_output_json": json.dumps(w_demo) if isinstance(w_demo, (dict, list)) else json.dumps({"output": str(w_demo)}),
                    "expected_features_json": json.dumps(w_expected) if isinstance(w_expected, list) else json.dumps([str(w_expected)]),
                    "deliverables_json": json.dumps(w_expected if isinstance(w_expected, list) else []),
                    "tasks": tasks_list
                })

        else:
            # 3 Month track: expect 4 phases converted to 12 weekly records
            if len(milestones) < 4:
                return False, f"3 Month task plan must contain 4 phases (covering weeks 1-12). Found {len(milestones)}.", None, None

            phase_ranges = [
                (1, "1-3", [1, 2, 3], "25%"),
                (2, "4-6", [4, 5, 6], "50%"),
                (3, "7-9", [7, 8, 9], "75%"),
                (4, "10-12", [10, 11, 12], "100%")
            ]

            for p_idx, (phase_num, default_label, week_nums, default_completion) in enumerate(phase_ranges):
                p_data = milestones[p_idx] if p_idx < len(milestones) else {}
                if not isinstance(p_data, dict):
                    p_data = {}

                p_title = (p_data.get("title") or f"Phase {phase_num}: Industrial Implementation").strip()
                p_weeks_label = (p_data.get("weeks") or default_label).strip()
                p_goal = (p_data.get("goal") or "").strip()
                p_completion = str(p_data.get("completion") or default_completion).strip()
                p_github = (p_data.get("github_requirement") or "").strip()
                p_condition = (p_data.get("completion_condition") or "").strip()
                p_demo = p_data.get("demo_output") or {}
                p_expected = p_data.get("expected_features") or []

                raw_tasks = p_data.get("tasks", [])
                if not isinstance(raw_tasks, list):
                    raw_tasks = [str(raw_tasks)] if raw_tasks else []

                # Convert raw tasks
                all_phase_tasks = []
                for t_idx, t_item in enumerate(raw_tasks, 1):
                    if isinstance(t_item, dict):
                        t_title = t_item.get("title") or t_item.get("task") or str(t_item)
                        t_desc = t_item.get("description") or ""
                    else:
                        t_title = str(t_item).strip()
                        t_desc = ""
                    if t_title:
                        all_phase_tasks.append({
                            "order_num": t_idx,
                            "title": t_title,
                            "description": t_desc,
                            "priority": "Medium",
                            "estimated_hours": 8.0
                        })

                # Distribute tasks across the 3 weeks of this phase
                tasks_per_week = {w: [] for w in week_nums}
                if all_phase_tasks:
                    for idx, t in enumerate(all_phase_tasks):
                        assigned_w = week_nums[idx % len(week_nums)]
                        tasks_per_week[assigned_w].append({
                            "order_num": len(tasks_per_week[assigned_w]) + 1,
                            "title": t["title"],
                            "description": t["description"],
                            "priority": t["priority"],
                            "estimated_hours": t["estimated_hours"]
                        })
                    total_tasks_count += len(all_phase_tasks)
                else:
                    for w in week_nums:
                        tasks_per_week[w].append({
                            "order_num": 1,
                            "title": f"Execute Week {w} objectives for {p_title}",
                            "description": p_goal,
                            "priority": "Medium",
                            "estimated_hours": 8.0
                        })
                        total_tasks_count += 1

                for w in week_nums:
                    normalized_weeks.append({
                        "week_number": w,
                        "title": f"Week {w}: {p_title}",
                        "phase_number": phase_num,
                        "phase_title": p_title,
                        "weeks_label": p_weeks_label,
                        "completion_percentage": p_completion,
                        "goal": p_goal,
                        "objective": f"Phase {phase_num} (Weeks {p_weeks_label}): {p_goal}",
                        "instructions": f"Follow the Phase {phase_num} roadmap. Satisfy github and completion requirements.",
                        "github_requirement": p_github,
                        "completion_condition": p_condition,
                        "demo_output_json": json.dumps(p_demo) if isinstance(p_demo, (dict, list)) else json.dumps({"output": str(p_demo)}),
                        "expected_features_json": json.dumps(p_expected) if isinstance(p_expected, list) else json.dumps([str(p_expected)]),
                        "deliverables_json": json.dumps(p_expected if isinstance(p_expected, list) else []),
                        "tasks": tasks_per_week[w]
                    })

        # 7. Check Duplicate Project / Problem ID
        existing_by_code = Project.query.filter_by(project_code=problem_id).first()
        existing_by_title = Project.query.filter(
            Project.title.ilike(project_title),
            Project.domain.ilike(domain),
            Project.duration_months == json_dur_months
        ).first()

        existing_project = existing_by_code or existing_by_title
        is_duplicate = existing_project is not None

        # 8. Extract all additional rich metadata
        level = (internship.get("level") or internship.get("difficulty") or "Easy to Medium").strip()
        project_type = (internship.get("project_type") or "Real-Time Application").strip()
        deployment = (internship.get("deployment") or "Localhost").strip()
        cloud_req = bool(internship.get("cloud_required", False))
        paid_api_req = bool(internship.get("paid_api_required", False))
        github_req = bool(internship.get("github_required", True))
        prob_statement = (internship.get("problem_statement") or "").strip()
        objective = (internship.get("objective") or "").strip()

        tech_list = internship.get("technologies") or []
        if not isinstance(tech_list, list):
            tech_list = [str(tech_list)]

        reqs = internship.get("requirements") or {}
        modules = internship.get("project_modules") or []
        restrictions = internship.get("restrictions") or []
        final_deliv = internship.get("final_deliverable") or {}
        eval_data = internship.get("evaluation") or {}

        parsed_payload = {
            "problem_id": problem_id,
            "project_title": project_title,
            "domain": domain,
            "duration_months": json_dur_months,
            "duration_weeks": total_weeks,
            "level": level,
            "project_type": project_type,
            "deployment": deployment,
            "cloud_required": cloud_req,
            "paid_api_required": paid_api_req,
            "github_required": github_req,
            "problem_statement": prob_statement,
            "objective": objective,
            "technologies": tech_list,
            "requirements": reqs,
            "project_modules": modules,
            "restrictions": restrictions,
            "final_deliverable": final_deliv,
            "evaluation": eval_data,
            "weeks": normalized_weeks,
            "source_json": json.dumps(data),
            "source_json_name": filename,
            "is_duplicate": is_duplicate,
            "existing_project_id": existing_project.id if existing_project else None,
            "existing_project_code": existing_project.project_code if existing_project else None
        }

        # Build preview summary for the UI
        preview_data = {
            "problem_id": problem_id,
            "project_title": project_title,
            "domain": domain,
            "duration_label": sel_dur_str,
            "duration_months": json_dur_months,
            "level": level,
            "project_type": project_type,
            "deployment": deployment,
            "total_weeks": total_weeks,
            "total_tasks": total_tasks_count,
            "is_duplicate": is_duplicate,
            "existing_project_id": existing_project.id if existing_project else None,
            "existing_project_code": existing_project.project_code if existing_project else None,
            "weeks": [
                {
                    "week_number": w["week_number"],
                    "phase_number": w["phase_number"],
                    "phase_title": w["phase_title"],
                    "weeks_label": w["weeks_label"],
                    "title": w["title"],
                    "completion_percentage": w["completion_percentage"],
                    "tasks_count": len(w["tasks"]),
                    "tasks": [t["title"] for t in w["tasks"]]
                }
                for w in normalized_weeks
            ]
        }

        return True, None, preview_data, parsed_payload

    @staticmethod
    def commit_import(parsed_payload, admin_user=None, overwrite=False):
        """
        Atomically commit the parsed project, weeks, tasks, and audit history to the database.
        Guarantees that either all records are written or a rollback occurs.
        """
        if not parsed_payload:
            raise ValueError("No task plan data provided for import.")

        problem_id = parsed_payload["problem_id"]
        project_title = parsed_payload["project_title"]
        domain = parsed_payload["domain"]
        duration_months = parsed_payload["duration_months"]
        duration_weeks = parsed_payload["duration_weeks"]
        filename = parsed_payload.get("source_json_name", "task_plan.json")

        try:
            # Check if project already exists
            existing_project = None
            if parsed_payload.get("existing_project_id"):
                existing_project = Project.query.get(parsed_payload["existing_project_id"])
            if not existing_project:
                existing_project = Project.query.filter_by(project_code=problem_id).first()

            if existing_project and not overwrite:
                raise ValueError(f"Project with Problem ID '{problem_id}' already exists. Select 'Update Existing Project' to overwrite.")

            if existing_project and overwrite:
                # Update existing project fields
                project = existing_project
                project.title = project_title
                project.domain = domain
                project.description = parsed_payload.get("objective") or parsed_payload.get("problem_statement") or f"{duration_months}-Month {domain} Project"
                project.problem_statement = parsed_payload.get("problem_statement")
                project.expected_outcome = parsed_payload.get("objective")
                project.objectives_json = json.dumps(parsed_payload.get("technologies", []))
                project.tech_stack_json = json.dumps(parsed_payload.get("technologies", []))
                project.requirements_json = json.dumps(parsed_payload.get("requirements", {}))
                project.instructions_md = f"Follow the {duration_weeks}-week structured milestone roadmap."
                project.reference_links_json = json.dumps([])
                project.project_type = parsed_payload.get("project_type")
                project.deployment = parsed_payload.get("deployment")
                project.cloud_required = parsed_payload.get("cloud_required", False)
                project.paid_api_required = parsed_payload.get("paid_api_required", False)
                project.github_required = parsed_payload.get("github_required", True)
                project.modules_json = json.dumps(parsed_payload.get("project_modules", []))
                project.restrictions_json = json.dumps(parsed_payload.get("restrictions", []))
                project.final_deliverable_json = json.dumps(parsed_payload.get("final_deliverable", {}))
                project.evaluation_json = json.dumps(parsed_payload.get("evaluation", {}))
                project.source_json = parsed_payload.get("source_json")
                project.source_json_name = filename
                project.difficulty = parsed_payload.get("level", "Intermediate")
                project.is_active = True
                project.updated_at = datetime.utcnow()

                # Clear old template weeks & tasks
                for pw in project.project_weeks.all():
                    db.session.delete(pw)
                db.session.flush()

                action_type = "UPDATED"
            else:
                # Create brand new Project
                project = Project(
                    project_code=problem_id,
                    title=project_title,
                    domain=domain,
                    description=parsed_payload.get("objective") or parsed_payload.get("problem_statement") or f"{duration_months}-Month {domain} Project",
                    problem_statement=parsed_payload.get("problem_statement"),
                    expected_outcome=parsed_payload.get("objective"),
                    objectives_json=json.dumps(parsed_payload.get("technologies", [])),
                    tech_stack_json=json.dumps(parsed_payload.get("technologies", [])),
                    requirements_json=json.dumps(parsed_payload.get("requirements", {})),
                    instructions_md=f"Follow the {duration_weeks}-week structured milestone roadmap.",
                    reference_links_json=json.dumps([]),
                    project_type=parsed_payload.get("project_type"),
                    deployment=parsed_payload.get("deployment"),
                    cloud_required=parsed_payload.get("cloud_required", False),
                    paid_api_required=parsed_payload.get("paid_api_required", False),
                    github_required=parsed_payload.get("github_required", True),
                    modules_json=json.dumps(parsed_payload.get("project_modules", [])),
                    restrictions_json=json.dumps(parsed_payload.get("restrictions", [])),
                    final_deliverable_json=json.dumps(parsed_payload.get("final_deliverable", {})),
                    evaluation_json=json.dumps(parsed_payload.get("evaluation", {})),
                    source_json=parsed_payload.get("source_json"),
                    source_json_name=filename,
                    duration_weeks=duration_weeks,
                    duration_months=duration_months,
                    difficulty=parsed_payload.get("level", "Intermediate"),
                    is_active=True
                )
                db.session.add(project)
                db.session.flush()
                action_type = "IMPORTED"

            # Create ProjectWeek & ProjectTask records
            total_tasks_created = 0
            for w_data in parsed_payload.get("weeks", []):
                pw = ProjectWeek(
                    project_id=project.id,
                    week_number=w_data["week_number"],
                    title=w_data["title"],
                    description=w_data.get("goal") or "",
                    objective=w_data.get("objective") or "",
                    instructions=w_data.get("instructions") or "",
                    deliverables_json=w_data.get("deliverables_json", "[]"),
                    phase_number=w_data.get("phase_number"),
                    phase_title=w_data.get("phase_title"),
                    weeks_label=w_data.get("weeks_label"),
                    completion_percentage=w_data.get("completion_percentage"),
                    goal=w_data.get("goal"),
                    expected_features_json=w_data.get("expected_features_json", "[]"),
                    demo_output_json=w_data.get("demo_output_json", "{}"),
                    github_requirement=w_data.get("github_requirement"),
                    completion_condition=w_data.get("completion_condition")
                )
                db.session.add(pw)
                db.session.flush()

                for t_data in w_data.get("tasks", []):
                    pt = ProjectTask(
                        week_id=pw.id,
                        title=t_data["title"],
                        description=t_data.get("description", ""),
                        instructions=t_data.get("instructions", ""),
                        expected_output=t_data.get("expected_output", ""),
                        priority=t_data.get("priority", "Medium"),
                        estimated_hours=t_data.get("estimated_hours", 8.0),
                        order_num=t_data.get("order_num", 1)
                    )
                    db.session.add(pt)
                    total_tasks_created += 1

            # Log to TaskImportHistory
            history = TaskImportHistory(
                filename=filename,
                project_id=project.id,
                project_code=project.project_code,
                project_title=project.title,
                domain=project.domain,
                duration_months=project.duration_months,
                total_weeks=duration_weeks,
                total_tasks=total_tasks_created,
                imported_by=admin_user.id if admin_user else None,
                status=action_type
            )
            db.session.add(history)

            db.session.commit()
            return project, action_type

        except Exception as e:
            db.session.rollback()
            logger.exception("Failed to atomically commit task plan import")
            raise e

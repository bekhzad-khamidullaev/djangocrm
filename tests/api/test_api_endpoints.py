from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from rest_framework.test import APIClient

from common.utils.helpers import get_today
from crm.models import Company, Contact, Deal, Lead
from crm.models.others import CallLog, Stage
from tasks.models import Project, Task, TaskStage, Tag as TaskTag
from tests.base_test_classes import BaseTestCase


User = get_user_model()


def api_url(name: str, *args) -> str:
    """Resolve an API route, supporting both legacy and current namespaces."""
    for ns in ("v1", "api"):
        try:
            return reverse(f"{ns}:{name}", args=args)
        except Exception:
            continue
    return reverse(name, args=args)


def _extract_results(data):
    return data.get("results", data)


class ApiBehaviorTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.other_client = APIClient()
        self.user = User.objects.get(username="Marina.Co-worker.Global")
        self.other_user = User.objects.get(username="Masha.Co-worker.Bookkeeping")
        self.client.force_authenticate(self.user)
        self.other_client.force_authenticate(self.other_user)

    def test_call_log_filters_and_scoping(self):
        own_log = CallLog.objects.create(
            user=self.user,
            direction="inbound",
            number="+100200",
            duration=25,
        )
        CallLog.objects.create(
            user=self.other_user,
            direction="outbound",
            number="+999000",
            duration=50,
        )

        url = api_url("calllog-list")
        response = self.client.get(url, {"direction": "inbound", "number": "1002"})
        self.assertEqual(response.status_code, 200, response.content)

        results = _extract_results(response.data)
        returned_ids = {item["id"] for item in results}
        self.assertIn(own_log.id, returned_ids)
        self.assertEqual(len(returned_ids), 1)

    def test_call_log_create_sets_owner(self):
        url = api_url("calllog-list")
        payload = {"direction": "outbound", "number": "+700", "duration": 5}
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, 201, response.content)

        call_id = response.data["id"]
        self.assertTrue(
            CallLog.objects.filter(id=call_id, user=self.user, number="+700").exists()
        )

    def test_dashboard_endpoints_include_owned_objects(self):
        company = Company.objects.create(
            full_name="Dashboard LLC",
            email="dash@example.com",
            owner=self.user,
        )
        contact = Contact.objects.create(
            first_name="Dash",
            last_name="User",
            email="dash.user@example.com",
            owner=self.user,
            company=company,
        )
        stage = Stage.objects.filter(default=True).first() or Stage.objects.first()
        deal = Deal.objects.create(
            name="Dashboard Deal",
            next_step="Call",
            next_step_date=get_today(),
            owner=self.user,
            stage=stage,
            company=company,
            contact=contact,
        )
        task_stage = TaskStage.objects.filter(default=True).first() or TaskStage.objects.first()
        task = Task.objects.create(
            name="Dashboard Task",
            next_step="Prepare",
            next_step_date=get_today(),
            owner=self.user,
            stage=task_stage,
        )
        task.responsible.add(self.user)

        analytics_url = api_url("dashboard-analytics")
        analytics_resp = self.client.get(analytics_url, {"period": "7d"})
        self.assertEqual(analytics_resp.status_code, 200, analytics_resp.content)
        analytics = analytics_resp.data
        self.assertIn("monthly_growth", analytics)
        self.assertGreaterEqual(analytics["monthly_growth"]["contacts"], 1)
        self.assertGreaterEqual(analytics["monthly_growth"]["companies"], 1)
        self.assertGreaterEqual(analytics["monthly_growth"]["deals"], 1)
        self.assertGreaterEqual(analytics["tasks"]["active"], 1)

        funnel_url = api_url("dashboard-funnel")
        funnel_resp = self.client.get(funnel_url, {"period": "30d"})
        self.assertEqual(funnel_resp.status_code, 200, funnel_resp.content)
        funnel_row = next(
            (row for row in funnel_resp.data if row["label"] == stage.name), None
        )
        self.assertIsNotNone(funnel_row)
        self.assertGreaterEqual(funnel_row["value"], 1)

        activity_url = api_url("dashboard-activity")
        activity_resp = self.client.get(activity_url, {"limit": 10})
        self.assertEqual(activity_resp.status_code, 200, activity_resp.content)
        self.assertTrue(
            any(deal.name in item.get("message", "") for item in activity_resp.data)
        )
        self.assertTrue(
            any(task.name in item.get("message", "") for item in activity_resp.data)
        )

    def test_lead_convert_creates_contact_company_and_deal(self):
        lead = Lead.objects.create(
            first_name="Lead",
            last_name="Example",
            email="lead@example.com",
            company_name="Lead Co",
            owner=self.user,
        )
        convert_url = api_url("lead-convert", lead.id)
        response = self.client.post(convert_url, {"create_deal": True}, format="json")
        self.assertEqual(response.status_code, 200, response.content)

        lead.refresh_from_db()
        self.assertTrue(lead.was_in_touch)
        self.assertIsNotNone(response.data["contact"])
        self.assertIsNotNone(response.data["company"])
        self.assertIsNotNone(response.data["deal"])

    def test_project_bulk_tag_adds_tags(self):
        content_type = ContentType.objects.get_for_model(Project)
        tag = TaskTag.objects.create(name="Priority", for_content=content_type)

        project_payload = {
            "name": "Project One",
            "next_step": "Ship",
            "next_step_date": date.today(),
        }
        p1_resp = self.client.post(api_url("project-list"), project_payload, format="json")
        self.assertEqual(p1_resp.status_code, 201, p1_resp.content)
        p2_resp = self.client.post(
            api_url("project-list"),
            {**project_payload, "name": "Project Two"},
            format="json",
        )
        self.assertEqual(p2_resp.status_code, 201, p2_resp.content)

        bulk_resp = self.client.post(
            api_url("project-bulk-tag"),
            {"ids": [p1_resp.data["id"], p2_resp.data["id"]], "tags": [tag.id]},
            format="json",
        )
        self.assertEqual(bulk_resp.status_code, 200, bulk_resp.content)
        self.assertEqual(bulk_resp.data["updated"], 2)

        self.assertTrue(
            Project.objects.get(id=p1_resp.data["id"]).tags.filter(id=tag.id).exists()
        )
        self.assertTrue(
            Project.objects.get(id=p2_resp.data["id"]).tags.filter(id=tag.id).exists()
        )

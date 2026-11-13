"""
Smoke tests: is every part of the estate up and answering?

These are the only tests the repo starts with. Heron itself has none.
"""


class TestEstateIsUp:
    """The backend, the legacy screens and the three downstream systems respond."""

    def test_health(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_systems_status_lists_four_systems(self, client):
        response = client.get("/api/systems/status")
        assert response.status_code == 200
        keys = [s["key"] for s in response.json()]
        assert keys == ["legacy", "underwriting", "claims", "finance"]

    def test_heron_main_menu_renders(self, client):
        response = client.get("/api/legacy/")
        assert response.status_code == 200
        assert "HERON POLICY ADMINISTRATION" in response.text

    def test_heron_policy_enquiry_lists_policies(self, client):
        response = client.get("/api/legacy/polenq")
        assert response.status_code == 200
        assert "poldsp?polno=LD" in response.text

    def test_downstream_systems_health(self, client):
        for system in ("underwriting", "claims", "finance"):
            response = client.get(f"/api/systems/{system}/health")
            assert response.status_code == 200
            assert response.json()["status"] == "up"

    def test_data_health_has_no_integrity_errors(self, client):
        response = client.get("/api/data/health")
        assert response.status_code == 200
        assert response.json()["error_count"] == 0

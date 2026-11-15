import os
import tempfile


async def authenticate_test(test):
    if not hasattr(test, "temp_dir"):
        temporary = tempfile.TemporaryDirectory()
        old = os.environ.get("LITLENS_DATA_DIR")
        os.environ["LITLENS_DATA_DIR"] = temporary.name
        def cleanup():
            if old is None:
                os.environ.pop("LITLENS_DATA_DIR", None)
            else:
                os.environ["LITLENS_DATA_DIR"] = old
            temporary.cleanup()
        test.addCleanup(cleanup)
    result = await test.client.post("/auth/register", json={
        "username": "researcher", "display_name": "Test Researcher", "password": "test-password-123",
    })
    test.assertEqual(result.status_code, 201, result.text)
    test.client.headers["Authorization"] = "Bearer " + result.json()["token"]
    response = await test.client.put("/settings", json={"provider": "local", "embeddings_enabled": False, "auto_analyze": False})
    test.assertEqual(response.status_code, 200, response.text)

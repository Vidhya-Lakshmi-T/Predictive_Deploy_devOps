// =============================================================================
// src/test/java/com/predictive/deploy/ApiIntegrationTest.java
//
// Java integration tests run by Maven during Jenkins pipeline.
// These call your FastAPI endpoints and verify:
//   1. Health endpoint responds
//   2. /track accepts events and returns confusion score
//   3. High confusion score triggers rollback flag
//   4. /version returns correct version info
// =============================================================================

package com.predictive.deploy;

import org.apache.http.HttpResponse;
import org.apache.http.client.methods.HttpGet;
import org.apache.http.client.methods.HttpPost;
import org.apache.http.entity.StringEntity;
import org.apache.http.impl.client.CloseableHttpClient;
import org.apache.http.impl.client.HttpClients;
import org.apache.http.util.EntityUtils;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.*;
import static org.junit.Assert.*;

public class ApiIntegrationTest {

    private static final String API_BASE =
        System.getProperty("api.base.url", "http://localhost:8000");

    private CloseableHttpClient client;
    private ObjectMapper mapper;

    @Before
    public void setUp() {
        client = HttpClients.createDefault();
        mapper = new ObjectMapper();
    }

    @After
    public void tearDown() throws Exception {
        client.close();
    }

    // ── Test 1: Health check ────────────────────────────────────────────────
    @Test
    public void testHealthEndpointReturns200() throws Exception {
        HttpGet request = new HttpGet(API_BASE + "/health");
        HttpResponse response = client.execute(request);

        int statusCode = response.getStatusLine().getStatusCode();
        assertEquals("Health endpoint should return 200", 200, statusCode);

        String body = EntityUtils.toString(response.getEntity());
        JsonNode json = mapper.readTree(body);
        assertEquals("healthy", json.get("status").asText());

        System.out.println("✅ Health check passed: " + body);
    }

    // ── Test 2: Track endpoint accepts events ───────────────────────────────
    @Test
    public void testTrackEndpointAcceptsEventsAndReturnsScore() throws Exception {
        HttpPost request = new HttpPost(API_BASE + "/track");
        request.setHeader("Content-Type", "application/json");

        String payload = "{"
            + "\"session_id\": \"maven-test-001\","
            + "\"events\": ["
            + "  {\"session_id\": \"maven-test-001\", \"event_type\": \"idle\", \"count\": 1}"
            + "]"
            + "}";
        request.setEntity(new StringEntity(payload));

        HttpResponse response = client.execute(request);
        int statusCode = response.getStatusLine().getStatusCode();
        assertEquals("Track endpoint should return 200", 200, statusCode);

        String body = EntityUtils.toString(response.getEntity());
        JsonNode json = mapper.readTree(body);

        assertTrue("Response should contain cognitive_load_index",
            json.has("cognitive_load_index"));
        assertTrue("Response should contain predicted_issue",
            json.has("predicted_issue"));

        double score = json.get("cognitive_load_index").asDouble();
        assertTrue("Score should be between 0 and 100", score >= 0 && score <= 100);

        System.out.println("✅ Track endpoint passed. Score: " + score);
    }

    // ── Test 3: High confusion triggers rollback ────────────────────────────
    @Test
    public void testHighConfusionTriggersPredictionHIGH() throws Exception {
        HttpPost request = new HttpPost(API_BASE + "/track");
        request.setHeader("Content-Type", "application/json");

        // Send all maximum confusion signals
        String sessionId = "maven-high-" + System.currentTimeMillis();
        String payload = "{"
            + "\"session_id\": \"" + sessionId + "\","
            + "\"events\": ["
            + "  {\"session_id\": \"" + sessionId + "\", \"event_type\": \"rage_click\", \"count\": 5},"
            + "  {\"session_id\": \"" + sessionId + "\", \"event_type\": \"scroll_oscillation\", \"count\": 5},"
            + "  {\"session_id\": \"" + sessionId + "\", \"event_type\": \"repeated_action\", \"count\": 5}"
            + "]"
            + "}";
        request.setEntity(new StringEntity(payload));

        HttpResponse response = client.execute(request);
        String body = EntityUtils.toString(response.getEntity());
        JsonNode json = mapper.readTree(body);

        double score = json.get("cognitive_load_index").asDouble();
        String prediction = json.get("predicted_issue").asText();

        assertTrue("High confusion should produce score >= 70", score >= 70.0);
        assertEquals("High confusion should predict HIGH", "HIGH", prediction);

        System.out.println("✅ High confusion test passed. Score: " + score + ", Prediction: " + prediction);
    }

    // ── Test 4: Version endpoint returns version info ───────────────────────
    @Test
    public void testVersionEndpointReturnsVersionInfo() throws Exception {
        HttpGet request = new HttpGet(API_BASE + "/version");
        HttpResponse response = client.execute(request);

        int statusCode = response.getStatusLine().getStatusCode();
        assertEquals("Version endpoint should return 200", 200, statusCode);

        String body = EntityUtils.toString(response.getEntity());
        JsonNode json = mapper.readTree(body);

        assertTrue("Response should contain active_version", json.has("active_version"));
        assertTrue("Response should contain is_stable", json.has("is_stable"));

        String version = json.get("active_version").asText();
        assertTrue("Version should be v1 or v2",
            version.equals("v1") || version.equals("v2"));

        System.out.println("✅ Version endpoint passed. Active: " + version);
    }

    // ── Test 5: Score history is accessible ─────────────────────────────────
    @Test
    public void testScoreHistoryEndpoint() throws Exception {
        HttpGet request = new HttpGet(API_BASE + "/score/history?limit=5");
        HttpResponse response = client.execute(request);

        int statusCode = response.getStatusLine().getStatusCode();
        assertEquals("Score history endpoint should return 200", 200, statusCode);

        System.out.println("✅ Score history endpoint accessible");
    }
}

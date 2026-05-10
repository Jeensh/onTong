package com.example.slabdesign.boot.integration;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.databind.node.ObjectNode;
import io.restassured.RestAssured;
import io.restassured.http.ContentType;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DynamicTest;
import org.junit.jupiter.api.TestFactory;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.stream.Stream;

import static io.restassured.RestAssured.given;
import static org.assertj.core.api.Assertions.assertThat;

/**
 * Tier 3 integration test — runs the 21-step algorithm end-to-end via REST
 * and asserts the JSON response matches a per-scenario golden file.
 *
 * Five fixtures (S1-S5) cover golden path / multi-split / A-a fallback / DG004
 * validation fail / minimal-active-process. The cmpCd/orgCd are 'K'/'1'.
 *
 * Modes:
 *   GOLDEN_REGEN=true  → write captured response to src/test/resources/golden/{id}.json
 *   default            → compare response against the locked golden
 *
 * Volatile fields normalized away before persisting the golden:
 *   trace[].elapsedMs, slabResults[].slabNo, slabResults[].createdAt.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class ScenarioGoldenTest {

    private static final ObjectMapper MAPPER = new ObjectMapper()
        .enable(SerializationFeature.INDENT_OUTPUT);
    private static final boolean REGEN = "true".equalsIgnoreCase(System.getenv("GOLDEN_REGEN"));

    @LocalServerPort int port;

    @BeforeEach
    void setup() {
        RestAssured.port = port;
        given().post("/api/sd/seed/reset").then().statusCode(200);
    }

    @TestFactory
    Stream<DynamicTest> scenarios() {
        return Stream.of(
            scenario("S1", "ORD20260510001"),
            scenario("S2", "ORD20260510002"),
            scenario("S3", "ORD20260510003"),
            scenario("S4", "ORD20260510004"),
            scenario("S5", "ORD20260510005")
        );
    }

    private DynamicTest scenario(String id, String orderNo) {
        return DynamicTest.dynamicTest(id, () -> {
            String body = """
                { "cmpCd": "K", "orgCd": "1", "orderNo": "%s" }
                """.formatted(orderNo);
            String response = given()
                .contentType(ContentType.JSON)
                .body(body)
                .when()
                .post("/api/sd/working/single?trace=true")
                .then()
                .statusCode(200)
                .extract().asString();

            Path goldenPath = Paths.get("src/test/resources/golden/" + id + ".json");
            JsonNode actual = MAPPER.readTree(normalizeVolatile(response));

            if (REGEN || !Files.exists(goldenPath) || Files.size(goldenPath) == 0) {
                Files.writeString(goldenPath, MAPPER.writeValueAsString(actual));
                System.out.println("[GOLDEN_REGEN] wrote " + goldenPath.toAbsolutePath());
                return;
            }

            JsonNode expected = MAPPER.readTree(Files.readString(goldenPath));
            assertThat(actual).isEqualTo(expected);
        });
    }

    private String normalizeVolatile(String json) throws IOException {
        JsonNode tree = MAPPER.readTree(json);
        if (tree.has("trace") && tree.get("trace").isArray()) {
            tree.get("trace").forEach(node -> {
                if (node.isObject()) {
                    ObjectNode obj = (ObjectNode) node;
                    obj.remove("elapsedMs");
                    // input/output snapshots may contain slabNo (sequence-derived)
                    scrubVolatileMap(obj.get("input"));
                    scrubVolatileMap(obj.get("output"));
                }
            });
        }
        if (tree.has("slabResults") && tree.get("slabResults").isArray()) {
            tree.get("slabResults").forEach(node -> {
                if (node.isObject()) {
                    ObjectNode obj = (ObjectNode) node;
                    if (obj.has("slabNo")) obj.put("slabNo", "__SEQ__");
                    if (obj.has("createdAt")) obj.put("createdAt", "__TS__");
                }
            });
        }
        return MAPPER.writeValueAsString(tree);
    }

    private void scrubVolatileMap(JsonNode node) {
        if (node == null || !node.isObject()) return;
        ObjectNode obj = (ObjectNode) node;
        if (obj.has("slabNo")) obj.put("slabNo", "__SEQ__");
    }
}

package com.example.agentdemo;

import org.springframework.boot.CommandLineRunner;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.http.MediaType;
import org.springframework.http.codec.ServerSentEvent;
import org.springframework.web.reactive.function.BodyInserters;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Flux;

import java.util.Map;

/**
 * Demonstrates that any OpenAI-compatible consumer (here: Spring Boot + WebClient)
 * can subscribe to the agent workflow's SSE stream directly.
 *
 * Run:
 *   mvn -q spring-boot:run \
 *     -Dspring-boot.run.arguments="Calculate 3 items at 129.9 each plus 15%% tax"
 */
@SpringBootApplication
public class AgentDemoApplication implements CommandLineRunner {

    private final WebClient client = WebClient.create("http://localhost:8000");

    public static void main(String[] args) {
        SpringApplication.run(AgentDemoApplication.class, args);
    }

    @Override
    public void run(String... args) {
        String task = (args.length > 0) ? String.join(" ", args)
                : "Calculate 3 items at 129.9 each plus 15% tax";

        System.out.println("== Task: " + task + " ==");

        Flux<ServerSentEvent<Map>> stream = client.post()
                .uri("/v1/agents/workflow/run")
                .contentType(MediaType.APPLICATION_JSON)
                .body(BodyInserters.fromValue(Map.of("task", task)))
                .retrieve()
                .bodyToFlux(new org.springframework.core.ParameterizedTypeReference<>() {
                });

        stream.doOnNext(event -> {
                    String type = event.event();
                    Object data = event.data();
                    System.out.println("event: " + type);
                    System.out.println("data:  " + data);
                    if ("approval.request".equals(type)) {
                        System.out.println(">> HITL: approve via "
                                + "POST /v1/agents/{session}/approve "
                                + "{action_id: " + data + "}");
                    }
                })
                .filter(event -> "agent.done".equals(event.event()) || "agent.error".equals(event.event()))
                .take(1)
                .blockLast();

        System.out.println("== stream closed ==");
    }
}
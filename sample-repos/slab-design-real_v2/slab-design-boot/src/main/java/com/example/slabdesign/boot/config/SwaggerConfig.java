package com.example.slabdesign.boot.config;

import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Info;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class SwaggerConfig {

    @Bean
    public OpenAPI slabDesignOpenApi() {
        return new OpenAPI().info(new Info()
            .title("slab-design-real_v2 API")
            .version("1.0.0")
            .description("21-step slab design with H2 in-memory DB and step-trace responses for simulation verification."));
    }
}

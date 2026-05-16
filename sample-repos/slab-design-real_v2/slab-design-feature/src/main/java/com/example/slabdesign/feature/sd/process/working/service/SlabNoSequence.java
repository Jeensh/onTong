package com.example.slabdesign.feature.sd.process.working.service;

import org.springframework.stereotype.Component;

import java.util.concurrent.atomic.AtomicLong;

/**
 * sd · slab 번호 시퀀스 — 12자리 zero-padded 숫자 문자열.
 *
 * 데모: in-memory AtomicLong, JVM 재시작 시 reset.
 * 실제 운영: DB 시퀀스 또는 분산 ID 생성기 (snowflake 등) 로 교체 필요.
 */
@Component
public class SlabNoSequence {

    private final AtomicLong counter = new AtomicLong(1);

    /** "000000000001", "000000000002", ... */
    public String next() {
        return String.format("%012d", counter.getAndIncrement());
    }
}

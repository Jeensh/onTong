package com.ontong.slab.service;

import com.ontong.slab.domain.OrderSpec;
import com.ontong.slab.optimizer.DesignCandidate;
import com.ontong.slab.optimizer.WeightMaximizer;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.NoSuchElementException;

/**
 * Slab 설계 서비스. 수주 사양을 받아 최대 중량 후보를 반환하는 파사드.
 *
 * 외부 호출부(REST 컨트롤러, 배치 잡 등)는 이 서비스 하나만 의존한다.
 */
@Service
public class SlabDesignService {

    private final WeightMaximizer optimizer;

    @Autowired
    public SlabDesignService(WeightMaximizer optimizer) {
        this.optimizer = optimizer;
    }

    /**
     * 수주 사양에 대한 최적 Slab 을 설계한다. 가능한 후보가 없으면 예외.
     */
    public DesignCandidate design(OrderSpec order) {
        return optimizer.findBest(order)
                .orElseThrow(() -> new NoSuchElementException("no feasible slab for order " + order.getOrderId()));
    }
}

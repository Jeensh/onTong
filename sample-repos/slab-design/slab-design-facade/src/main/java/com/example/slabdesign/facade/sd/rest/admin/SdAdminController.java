package com.example.slabdesign.facade.sd.rest.admin;

import com.example.slabdesign.feature.sd.designer.SdDesigner;
import com.example.slabdesign.feature.sd.process.working.action.SdOrderExtractor;
import com.example.slabdesign.store.sd.history.oracle.jpo.SlabDesignHistJpo;
import com.example.slabdesign.store.sd.history.oracle.repository.SlabDesignHistRepository;
import com.example.slabdesign.store.sd.working.domain.entity.SDSlabEntity;
import com.example.slabdesign.store.sd.working.oracle.jpo.SDOrderPK;
import com.example.slabdesign.store.sd.std.oracle.jpo.CastSpecJpo;
import com.example.slabdesign.store.sd.std.oracle.jpo.CustomerStdJpo;
import com.example.slabdesign.store.sd.std.oracle.jpo.EdgingGroupJpo;
import com.example.slabdesign.store.sd.std.oracle.jpo.EdgingSpecJpo;
import com.example.slabdesign.store.sd.std.oracle.jpo.HrMaxWgtJpo;
import com.example.slabdesign.store.sd.std.oracle.jpo.HrMinWgtJpo;
import com.example.slabdesign.store.sd.std.oracle.jpo.HrSpecJpo;
import com.example.slabdesign.store.sd.std.oracle.jpo.SdProductivityStdJpo;
import com.example.slabdesign.store.sd.std.oracle.repository.CastSpecRepository;
import com.example.slabdesign.store.sd.std.oracle.repository.CustomerStdRepository;
import com.example.slabdesign.store.sd.std.oracle.repository.EdgingGroupRepository;
import com.example.slabdesign.store.sd.std.oracle.repository.EdgingSpecRepository;
import com.example.slabdesign.store.sd.std.oracle.repository.HrMaxWgtRepository;
import com.example.slabdesign.store.sd.std.oracle.repository.HrMinWgtRepository;
import com.example.slabdesign.store.sd.std.oracle.repository.HrSpecRepository;
import com.example.slabdesign.store.sd.std.oracle.repository.SdProductivityStdRepository;
import com.example.slabdesign.store.sd.working.oracle.jpo.SDOrderChemicalJpo;
import com.example.slabdesign.store.sd.working.oracle.jpo.SDOrderOmJpo;
import com.example.slabdesign.store.sd.working.oracle.jpo.SDOrderOsJpo;
import com.example.slabdesign.store.sd.working.oracle.jpo.SDOrderQdJpo;
import com.example.slabdesign.store.sd.working.oracle.jpo.SlabResultJpo;
import com.example.slabdesign.store.sd.working.oracle.repository.SDOrderChemicalRepository;
import com.example.slabdesign.store.sd.working.oracle.repository.SDOrderOmRepository;
import com.example.slabdesign.store.sd.working.oracle.repository.SDOrderOsRepository;
import com.example.slabdesign.store.sd.working.oracle.repository.SDOrderQdRepository;
import com.example.slabdesign.store.sd.working.oracle.repository.SlabResultRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * sd · admin · DB 데이터 조회 read API.
 *
 * H2 데모 환경에서 slab 설계 시스템의 입력/결과/이력 데이터를 화면으로 보여주기 위한 admin 엔드포인트.
 * 14 테이블 모두 GET 으로 노출. 별도 인증 없음 (데모 전용).
 *
 * CORS: localhost:3000 (onTong 프론트) 에서 호출 가능.
 */
@RestController
@RequestMapping("/api/sd/admin")
@CrossOrigin(origins = "*")
public class SdAdminController {

    private final SDOrderOsRepository orderOsRepo;
    private final SDOrderOmRepository orderOmRepo;
    private final SDOrderQdRepository orderQdRepo;
    private final SDOrderChemicalRepository orderChemRepo;

    private final CastSpecRepository castSpecRepo;
    private final HrSpecRepository hrSpecRepo;
    private final HrMinWgtRepository hrMinWgtRepo;
    private final HrMaxWgtRepository hrMaxWgtRepo;
    private final EdgingSpecRepository edgingSpecRepo;
    private final EdgingGroupRepository edgingGroupRepo;
    private final SdProductivityStdRepository productivityRepo;
    private final CustomerStdRepository customerRepo;

    private final SlabResultRepository slabResultRepo;
    private final SlabDesignHistRepository historyRepo;

    private final SdDesigner designer;
    private final SdOrderExtractor extractor;

    @Autowired
    public SdAdminController(
            SDOrderOsRepository orderOsRepo,
            SDOrderOmRepository orderOmRepo,
            SDOrderQdRepository orderQdRepo,
            SDOrderChemicalRepository orderChemRepo,
            CastSpecRepository castSpecRepo,
            HrSpecRepository hrSpecRepo,
            HrMinWgtRepository hrMinWgtRepo,
            HrMaxWgtRepository hrMaxWgtRepo,
            EdgingSpecRepository edgingSpecRepo,
            EdgingGroupRepository edgingGroupRepo,
            SdProductivityStdRepository productivityRepo,
            CustomerStdRepository customerRepo,
            SlabResultRepository slabResultRepo,
            SlabDesignHistRepository historyRepo,
            SdDesigner designer,
            SdOrderExtractor extractor) {
        this.designer = designer;
        this.extractor = extractor;
        this.orderOsRepo = orderOsRepo;
        this.orderOmRepo = orderOmRepo;
        this.orderQdRepo = orderQdRepo;
        this.orderChemRepo = orderChemRepo;
        this.castSpecRepo = castSpecRepo;
        this.hrSpecRepo = hrSpecRepo;
        this.hrMinWgtRepo = hrMinWgtRepo;
        this.hrMaxWgtRepo = hrMaxWgtRepo;
        this.edgingSpecRepo = edgingSpecRepo;
        this.edgingGroupRepo = edgingGroupRepo;
        this.productivityRepo = productivityRepo;
        this.customerRepo = customerRepo;
        this.slabResultRepo = slabResultRepo;
        this.historyRepo = historyRepo;
    }

    /** 14 테이블 row 카운트 한방에. */
    @GetMapping("/counts")
    public Map<String, Long> counts() {
        return Map.ofEntries(
                Map.entry("ORDER_OS",          orderOsRepo.count()),
                Map.entry("ORDER_OM",          orderOmRepo.count()),
                Map.entry("ORDER_QD",          orderQdRepo.count()),
                Map.entry("ORDER_CHEMICAL",    orderChemRepo.count()),
                Map.entry("CAST_SPEC",         castSpecRepo.count()),
                Map.entry("HR_SPEC",           hrSpecRepo.count()),
                Map.entry("HR_MIN_WGT",        hrMinWgtRepo.count()),
                Map.entry("HR_MAX_WGT",        hrMaxWgtRepo.count()),
                Map.entry("EDGING_SPEC",       edgingSpecRepo.count()),
                Map.entry("EDGING_GROUP",      edgingGroupRepo.count()),
                Map.entry("SD_PRODUCTIVITY_STD", productivityRepo.count()),
                Map.entry("CUSTOMER_STD",      customerRepo.count()),
                Map.entry("SLAB_RESULT",       slabResultRepo.count()),
                Map.entry("SLAB_DESIGN_HIST",  historyRepo.count())
        );
    }

    // ── 주문 4종 ─────────────────────────────────────────────
    @GetMapping("/orders/os")        public List<SDOrderOsJpo>       orderOs()       { return orderOsRepo.findAll(); }
    @GetMapping("/orders/om")        public List<SDOrderOmJpo>       orderOm()       { return orderOmRepo.findAll(); }
    @GetMapping("/orders/qd")        public List<SDOrderQdJpo>       orderQd()       { return orderQdRepo.findAll(); }
    @GetMapping("/orders/chemical")  public List<SDOrderChemicalJpo> orderChemical() { return orderChemRepo.findAll(); }

    // ── 표준/사양 8종 ─────────────────────────────────────────
    @GetMapping("/spec/cast")        public List<CastSpecJpo>           castSpec()    { return castSpecRepo.findAll(); }
    @GetMapping("/spec/hr")          public List<HrSpecJpo>             hrSpec()      { return hrSpecRepo.findAll(); }
    @GetMapping("/spec/hr-min-wgt")  public List<HrMinWgtJpo>           hrMinWgt()    { return hrMinWgtRepo.findAll(); }
    @GetMapping("/spec/hr-max-wgt")  public List<HrMaxWgtJpo>           hrMaxWgt()    { return hrMaxWgtRepo.findAll(); }
    @GetMapping("/spec/edging")      public List<EdgingSpecJpo>         edgingSpec()  { return edgingSpecRepo.findAll(); }
    @GetMapping("/spec/edging-group") public List<EdgingGroupJpo>       edgingGroup() { return edgingGroupRepo.findAll(); }
    @GetMapping("/spec/productivity") public List<SdProductivityStdJpo> productivity(){ return productivityRepo.findAll(); }
    @GetMapping("/spec/customer")    public List<CustomerStdJpo>        customer()    { return customerRepo.findAll(); }

    // ── 결과/이력 2종 ─────────────────────────────────────────
    @GetMapping("/results")          public List<SlabResultJpo>      slabResults() { return slabResultRepo.findAll(); }
    @GetMapping("/history")          public List<SlabDesignHistJpo>  history()     { return historyRepo.findAll(); }

    /**
     * ★ 단일 주문 ad-hoc 설계 — Postman / curl JSON 테스트용.
     *
     * Request body: {"cmpCd":"K","orgCd":"K","orderNo":"TC01-NORMAL    "}
     *   - 미리 시드된 (또는 별도로 INSERT 한) 주문 1건의 PK 만 보내면 SdDesigner.design() 즉시 실행.
     *   - history/result 테이블에 즉시 누적 → /admin/history /admin/results 에서 확인.
     *
     * Response:
     *   - status: success | skipped | not_found
     *   - slab: SDSlabEntity (성공 시) / null (skip)
     *   - history: 이번 호출이 생성한 SLAB_DESIGN_HIST 새 row 들
     */
    @PostMapping("/test-design")
    public Map<String, Object> testDesign(@RequestBody Map<String, String> req) {
        String cmpCd   = req.getOrDefault("cmpCd", "K");
        String orgCd   = req.getOrDefault("orgCd", "K");
        String orderNo = req.get("orderNo");

        Map<String, Object> resp = new HashMap<>();
        resp.put("cmpCd",   cmpCd);
        resp.put("orgCd",   orgCd);
        resp.put("orderNo", orderNo);

        if (orderNo == null || orderNo.isEmpty()) {
            resp.put("status",  "not_found");
            resp.put("message", "orderNo is required");
            return resp;
        }

        SDOrderPK pk = new SDOrderPK(cmpCd, orgCd, orderNo);
        Optional<com.example.slabdesign.store.sd.working.oracle.jpo.SDOrderOsJpo> osOpt = orderOsRepo.findById(pk);
        if (osOpt.isEmpty()) {
            resp.put("status",  "not_found");
            resp.put("message", "ORDER_OS row not found for orderNo=" + orderNo);
            return resp;
        }

        long histBefore = historyRepo.count();
        long resBefore  = slabResultRepo.count();

        // SdOrderExtractor 가 4 JPO → SDOrderEntity 통합 (단일 PK 로 lookup)
        var entity = extractor.extractByPk(cmpCd, orgCd, orderNo);
        if (entity == null) {
            resp.put("status",  "not_found");
            resp.put("message", "SDOrderEntity 통합 실패 — 4 JPO 중 일부 NULL?");
            return resp;
        }

        SDSlabEntity slab;
        try {
            slab = designer.design(entity);
        } catch (RuntimeException ex) {
            resp.put("status",  "error");
            resp.put("error",   ex.getClass().getSimpleName());
            resp.put("message", ex.getMessage());
            // 새로 추가된 history row 만 반환
            resp.put("history", historyRepo.findAll().stream()
                .skip(histBefore).toList());
            return resp;
        }

        long histAfter = historyRepo.count();
        long resAfter  = slabResultRepo.count();

        resp.put("status", slab != null ? "success" : "skipped");
        resp.put("slab",   slab);
        resp.put("counts", Map.of(
            "history_added", histAfter - histBefore,
            "result_added",  resAfter  - resBefore));
        // 이번 호출로 추가된 history row 만 잘라서 반환
        List<SlabDesignHistJpo> all = historyRepo.findAll();
        resp.put("history", all.stream().skip(histBefore).toList());
        return resp;
    }

    /** 결과/이력 일괄 삭제 (test 사이클 초기화). */
    @PostMapping("/clear-results")
    public Map<String, Object> clearResults() {
        long histN = historyRepo.count();
        long resN  = slabResultRepo.count();
        historyRepo.deleteAll();
        slabResultRepo.deleteAll();
        return Map.of(
            "history_deleted", histN,
            "result_deleted",  resN);
    }
}

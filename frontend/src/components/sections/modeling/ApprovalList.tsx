"use client";

import React, { useCallback, useEffect, useState } from "react";
import { CheckSquare, Loader2, Check, X, ArrowRight } from "lucide-react";
import { getPendingReviews, approveReview, rejectReview, type ReviewRequest } from "@/lib/api/modeling";

const STATUS_BADGE: Record<string, string> = {
  pending: "bg-amber-100 dark:bg-amber-950/40 text-amber-700 dark:text-amber-400",
  approved: "bg-green-100 dark:bg-green-950/40 text-green-700 dark:text-green-400",
  rejected: "bg-red-100 dark:bg-red-950/40 text-red-700 dark:text-red-400",
};

export function ApprovalList({ repoId }: { repoId: string }) {
  const [reviews, setReviews] = useState<ReviewRequest[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [processing, setProcessing] = useState<string | null>(null);

  // Reject form state
  const [rejectingId, setRejectingId] = useState<string | null>(null);
  const [rejectComment, setRejectComment] = useState("");

  const fetchReviews = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getPendingReviews(repoId);
      setReviews(data.reviews);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [repoId]);

  useEffect(() => {
    fetchReviews();
  }, [fetchReviews]);

  const handleApprove = async (review: ReviewRequest) => {
    setProcessing(review.id);
    setError(null);
    try {
      await approveReview(review.id, "current-user");
      await fetchReviews();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setProcessing(null);
    }
  };

  const handleReject = async (reviewId: string) => {
    if (!rejectComment.trim()) return;
    setProcessing(reviewId);
    setError(null);
    try {
      await rejectReview(reviewId, "current-user", rejectComment.trim());
      setRejectingId(null);
      setRejectComment("");
      await fetchReviews();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setProcessing(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold mb-1">검토 요청</h2>
          <p className="text-sm text-muted-foreground">
            매핑 관리에서 제출된 검토 요청을 승인하거나 반려합니다.
          </p>
        </div>
        <button
          onClick={fetchReviews}
          disabled={loading}
          className="inline-flex items-center gap-1 rounded-md bg-primary px-3 py-1.5 text-xs text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {loading ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
          새로고침
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-lg border border-red-300 dark:border-red-800 bg-red-50 dark:bg-red-950/20 p-3 text-sm text-red-700 dark:text-red-400">
          {error}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center py-12 text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin mr-2" />
          Loading...
        </div>
      )}

      {/* Empty state */}
      {!loading && reviews.length === 0 && !error && (
        <div className="text-center py-12 text-muted-foreground space-y-2">
          <CheckSquare className="h-8 w-8 mx-auto mb-2 opacity-30" />
          <p className="text-sm">대기 중인 검토 요청이 없습니다.</p>
          <p className="text-xs">
            &ldquo;매핑 관리&rdquo; 탭에서 매핑을 추가한 뒤 검토를 요청하세요.
          </p>
        </div>
      )}

      {/* Review list */}
      {!loading && reviews.length > 0 && (
        <div className="space-y-3">
          {reviews.map((review) => {
            const isProcessing = processing === review.id;
            const isRejecting = rejectingId === review.id;

            return (
              <div key={review.id} className="rounded-lg border border-border bg-card p-4 space-y-3">
                {/* Mapping info */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-sm">
                    <span className="font-mono font-medium">{review.mapping_code}</span>
                    <ArrowRight className="h-3.5 w-3.5 text-muted-foreground" />
                    <span className="font-mono font-medium">{review.mapping_domain}</span>
                  </div>
                  <span className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-medium ${STATUS_BADGE[review.status] || STATUS_BADGE.pending}`}>
                    {review.status}
                  </span>
                </div>

                {/* Meta */}
                <div className="flex items-center gap-4 text-xs text-muted-foreground">
                  <span>요청자: <strong>{review.requested_by}</strong></span>
                  {review.reviewer && <span>검토자: <strong>{review.reviewer}</strong></span>}
                  {review.comment && <span>사유: {review.comment}</span>}
                </div>

                {/* Actions */}
                {review.status === "pending" && (
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleApprove(review)}
                      disabled={isProcessing}
                      className="inline-flex items-center gap-1 rounded-md bg-green-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-green-700 disabled:opacity-50"
                    >
                      {isProcessing ? <Loader2 className="h-3 w-3 animate-spin" /> : <Check className="h-3 w-3" />}
                      승인
                    </button>
                    {!isRejecting ? (
                      <button
                        onClick={() => setRejectingId(review.id)}
                        disabled={isProcessing}
                        className="inline-flex items-center gap-1 rounded-md border border-red-300 dark:border-red-800 text-red-600 dark:text-red-400 px-3 py-1.5 text-xs font-medium hover:bg-red-50 dark:hover:bg-red-950/30 disabled:opacity-50"
                      >
                        <X className="h-3 w-3" />
                        반려
                      </button>
                    ) : (
                      <div className="flex items-center gap-2 flex-1">
                        <input
                          type="text"
                          value={rejectComment}
                          onChange={(e) => setRejectComment(e.target.value)}
                          placeholder="반려 사유를 입력하세요..."
                          className="flex-1 px-2 py-1 text-xs bg-background border border-border rounded"
                          autoFocus
                        />
                        <button
                          onClick={() => handleReject(review.id)}
                          disabled={isProcessing || !rejectComment.trim()}
                          className="inline-flex items-center gap-1 rounded-md bg-red-600 px-3 py-1 text-xs font-medium text-white hover:bg-red-700 disabled:opacity-50"
                        >
                          {isProcessing ? <Loader2 className="h-3 w-3 animate-spin" /> : <X className="h-3 w-3" />}
                          확인
                        </button>
                        <button
                          onClick={() => { setRejectingId(null); setRejectComment(""); }}
                          className="text-xs text-muted-foreground hover:text-foreground"
                        >
                          취소
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

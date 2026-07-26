# Plan: "Load More Outfits" with Client-Side Cache

## Overview
Add pagination support to outfit suggestions so users can load more outfits without redundant API calls. Cache results client-side.

## Files to Modify

### 1. `server/app/pairing_engine.py`

**Change:** Add `offset` parameter, return dict with `items` + `total`

```python
# Line 1088: Update function signature
def suggest_outfits(
    db: Session,
    user_id: int,
    occasion_tag: str | None = None,
    target_gender: str | None = None,
    limit: int = 5,
    items: list[ClothingItem] | None = None,
    offset: int = 0,
) -> dict:  # Changed from list[OutfitSuggestion] to dict
```

**Change:** Update return statement (around line 1260-1263)

```python
# Before:
#     if len(results) >= limit:
#         break
# 
# return results

# After:
    # ... existing loop ...
    if len(results) >= limit + offset:
        break

total = len(results)
sliced = results[offset : offset + limit]
return {"items": sliced, "total": total}
```

### 2. `server/app/routers/outfits.py`

**Change:** Add `offset` param, new response model (lines 19-48)

```python
class OutfitSuggestionsResponse(BaseModel):
    outfits: list[OutfitSuggestionResponse]
    total: int

@router.get("/outfit-suggestions", response_model=OutfitSuggestionsResponse)
def get_outfit_suggestions(
    user_id: int = 1,
    occasion_tag: str | None = None,
    target_gender: str | None = None,
    limit: int = 5,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    result = suggest_outfits(db, user_id, occasion_tag, target_gender, limit, offset=offset)
    return OutfitSuggestionsResponse(
        outfits=[_to_response(r) for r in result["items"]],
        total=result["total"],
    )
```

**Change:** Update all other callers of `suggest_outfits` in this file (lines 47, 97-108, 144, 153)

Each call needs to unpack `result["items"]`:
- Line 47: `result = suggest_outfits(...)` → `result = suggest_outfits(...); items = result["items"]`
- Line 97-108: Same pattern
- Line 144: `results = suggest_outfits(db, user_id, limit=1)` → `results = suggest_outfits(db, user_id, limit=1)["items"]`
- Line 153: Same pattern

### 3. `app/lib/api.ts`

**Change:** Update `outfitApi.suggest()` return type (lines 235-243)

```typescript
export const outfitApi = {
  suggest: (params?: { occasion_tag?: string; target_gender?: string; limit?: number; offset?: number }) => {
    const query = new URLSearchParams();
    query.set("user_id", String(DEMO_USER_ID));
    if (params?.occasion_tag) query.set("occasion_tag", params.occasion_tag);
    if (params?.target_gender) query.set("target_gender", params.target_gender);
    if (params?.limit) query.set("limit", String(params.limit));
    if (params?.offset) query.set("offset", String(params.offset));
    return apiFetch<{ outfits: OutfitSuggestion[]; total: number }>(`/outfit-suggestions?${query.toString()}`);
  },
  // ... rest unchanged
};
```

### 4. `app/app/(tabs)/outfit-suggestions.tsx`

**Change:** Add new state variables (after line 253)

```typescript
const [cachedOutfits, setCachedOutfits] = useState<OutfitSuggestion[]>([]);
const [totalCount, setTotalCount] = useState(0);
const [loadingMore, setLoadingMore] = useState(false);
```

**Change:** Update `loadSuggestions` function (lines 282-296)

```typescript
const loadSuggestions = useCallback(async () => {
    setLoading(true);
    try {
      const data = await outfitApi.suggest({
        occasion_tag: selectedOccasion || undefined,
        target_gender: selectedTargetGender || undefined,
        limit: 5,
        offset: 0,
      });
      setCachedOutfits(data.outfits);
      setTotalCount(data.total);
      setSmartResult(null);
    } catch (e: any) {
      Alert.alert("Error", e.message);
    } finally {
      setLoading(false);
    }
  }, [selectedOccasion, selectedTargetGender]);
```

**Change:** Add `loadMore` function (after `loadSuggestions`)

```typescript
const loadMore = useCallback(async () => {
    if (loadingMore || cachedOutfits.length >= totalCount) return;
    setLoadingMore(true);
    try {
      const data = await outfitApi.suggest({
        occasion_tag: selectedOccasion || undefined,
        target_gender: selectedTargetGender || undefined,
        limit: 5,
        offset: cachedOutfits.length,
      });
      setCachedOutfits((prev) => [...prev, ...data.outfits]);
    } catch (e: any) {
      Alert.alert("Error", e.message);
    } finally {
      setLoadingMore(false);
    }
  }, [selectedOccasion, selectedTargetGender, cachedOutfits.length, totalCount, loadingMore]);
```

**Change:** Replace `suggestions` with `cachedOutfits` in render (line 855-861)

```typescript
// Before:
// {suggestions.map((item, index) => (
//   <View key={`suggestion-${index}`}>{renderCard({ item, index })}</View>
// ))}

// After:
{cachedOutfits.map((item, index) => (
  <View key={`suggestion-${index}`}>{renderCard({ item, index })}</View>
))}

{/* Load More button */}
{cachedOutfits.length < totalCount && (
  <TouchableOpacity
    style={styles.loadMoreBtn}
    onPress={loadMore}
    disabled={loadingMore}
  >
    {loadingMore ? (
      <ActivityIndicator size="small" color="#fff" />
    ) : (
      <Text style={styles.loadMoreBtnText}>Load More Outfits</Text>
    )}
  </TouchableOpacity>
)}
```

**Change:** Add styles for Load More button (in StyleSheet)

```typescript
loadMoreBtn: {
  backgroundColor: colors.accent,
  borderRadius: br.md,
  paddingVertical: spacing.sm + 2,
  alignItems: "center",
  marginTop: spacing.sm,
},
loadMoreBtnText: {
  color: colors.text.white,
  fontSize: fontSize.sm,
  fontWeight: fontWeight.semibold,
},
```

## Data Flow

```
1. Screen focuses → loadSuggestions()
   → GET /outfit-suggestions?offset=0&limit=5
   → cachedOutfits = [outfit1..outfit5], totalCount = 15

2. User taps "Load More Outfits"
   → GET /outfit-suggestions?offset=5&limit=5
   → cachedOutfits = [outfit1..outfit10]

3. User taps "Load More" again
   → GET /outfit-suggestions?offset=10&limit=5
   → cachedOutfits = [outfit1..outfit15]
   → Button hidden (15 >= 15)

4. User taps "Refresh" (header)
   → loadSuggestions() → offset=0&limit=5
   → cachedOutfits reset to [outfit1..outfit5]
```

## Testing

1. Start server: `cd server && python -m uvicorn app.main:app --reload`
2. Test API: `curl "http://localhost:8000/outfit-suggestions?user_id=1&limit=2&offset=0"` → should return `{outfits: [...], total: N}`
3. Test pagination: `curl "http://localhost:8000/outfit-suggestions?user_id=1&limit=2&offset=2"` → next 2 outfits
4. Test frontend: Open app → tap "Load More Outfits" → verify new cards appear
5. Test refresh: Tap "Refresh" → verify list resets to first 5

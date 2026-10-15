import { page } from '../storage/database.js';
import { normalizeText } from '../domain/models.js';

export async function search(query, { signal, kind, limit = 50, onProgress } = {}) {
  const normalized = normalizeText(query);
  const words = normalized.split(' ').filter(Boolean);
  if (!words.length) return [];
  let after = null;
  let results = [];
  do {
    if (signal?.aborted) return [];
    const batch = await page('searchEntries', { index: null, direction: 'next', after, limit: 200 });
    for (const record of batch.records) {
      if (kind && kind !== record.entityType || !words.every(word => record.textNormalized.includes(word))) continue;
      const score = record.titleNormalized === normalized ? 100 : record.titleNormalized.startsWith(normalized) ? 80 : words.every(word => record.titleNormalized.includes(word)) ? 60 : words.every(word => record.tagsNormalized.includes(word)) ? 40 : 20;
      results.push({ ...record, score });
    }
    results.sort((a, b) => b.score - a.score || b.updatedAt.localeCompare(a.updatedAt));
    results = results.slice(0, limit);
    after = batch.next;
    onProgress?.(results, Boolean(after));
    if (after) await new Promise(resolve => setTimeout(resolve, 0));
  } while (after);
  return signal?.aborted ? [] : results;
}

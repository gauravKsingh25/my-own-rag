'use client';

import { useState, useEffect, useCallback } from 'react';
import { getHealth, getReadiness, getRootInfo } from '@/lib/api/health';
import { HEALTH_REFRESH_INTERVAL } from '@/lib/utils/constants';

export function useHealth() {
  const [health, setHealth] = useState(null);
  const [readiness, setReadiness] = useState(null);
  const [rootInfo, setRootInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastChecked, setLastChecked] = useState(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [h, r, root] = await Promise.all([
        getHealth().catch(() => null),
        getReadiness().catch(() => null),
        getRootInfo().catch(() => null),
      ]);
      setHealth(h);
      setReadiness(r);
      setRootInfo(root);
      setLastChecked(new Date());
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, HEALTH_REFRESH_INTERVAL);
    return () => clearInterval(id);
  }, [refresh]);

  const isHealthy =
    health?.status === 'healthy' &&
    readiness?.status === 'ready';

  return { health, readiness, rootInfo, loading, error, lastChecked, refresh, isHealthy };
}

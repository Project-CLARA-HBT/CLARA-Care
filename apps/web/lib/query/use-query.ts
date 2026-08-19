"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { isProfileScopedKey } from "./query-keys";
import { PROFILE_CONTEXT_CHANGE_EVENT } from "@/lib/profile-context";

export interface UseQueryOptions<TData, TError = Error> {
  queryKey: readonly unknown[];
  queryFn: (context?: { signal?: AbortSignal }) => Promise<TData>;
  enabled?: boolean;
  refetchOnWindowFocus?: boolean;
  initialData?: TData;
  onSuccess?: (data: TData) => void;
  onError?: (error: TError) => void;
}

export interface UseQueryResult<TData, TError = Error> {
  data: TData | undefined;
  error: TError | null;
  isLoading: boolean;
  isFetching: boolean;
  isError: boolean;
  isSuccess: boolean;
  status: "pending" | "error" | "success";
  refetch: () => Promise<UseQueryResult<TData, TError>>;
}

export function useQuery<TData, TError = Error>(
  options: UseQueryOptions<TData, TError>,
): UseQueryResult<TData, TError> {
  const {
    queryKey,
    queryFn,
    enabled = true,
    initialData,
    onSuccess,
    onError,
  } = options;

  const [data, setData] = useState<TData | undefined>(initialData);
  const [error, setError] = useState<TError | null>(null);
  const [status, setStatus] = useState<"pending" | "error" | "success">(
    initialData !== undefined ? "success" : "pending",
  );
  const [isFetching, setIsFetching] = useState<boolean>(false);

  const dataRef = useRef(data);
  dataRef.current = data;
  const errorRef = useRef(error);
  errorRef.current = error;
  const statusRef = useRef(status);
  statusRef.current = status;

  const queryFnRef = useRef(queryFn);
  queryFnRef.current = queryFn;
  const onSuccessRef = useRef(onSuccess);
  onSuccessRef.current = onSuccess;
  const onErrorRef = useRef(onError);
  onErrorRef.current = onError;

  const keyString = JSON.stringify(queryKey);
  const abortControllerRef = useRef<AbortController | null>(null);

  const executeFetch = useCallback(async (): Promise<UseQueryResult<TData, TError>> => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    setIsFetching(true);
    try {
      const result = await queryFnRef.current({ signal: controller.signal });
      if (!controller.signal.aborted) {
        setData(result);
        setError(null);
        setStatus("success");
        setIsFetching(false);
        onSuccessRef.current?.(result);
        return {
          data: result,
          error: null,
          isLoading: false,
          isFetching: false,
          isError: false,
          isSuccess: true,
          status: "success",
          refetch: executeFetch,
        };
      }
    } catch (err: unknown) {
      if (!controller.signal.aborted) {
        const errorObj = (err instanceof Error ? err : new Error(String(err))) as TError;
        setError(errorObj);
        setStatus("error");
        setIsFetching(false);
        onErrorRef.current?.(errorObj);
        return {
          data: undefined,
          error: errorObj,
          isLoading: false,
          isFetching: false,
          isError: true,
          isSuccess: false,
          status: "error",
          refetch: executeFetch,
        };
      }
    }
    return {
      data: dataRef.current,
      error: errorRef.current,
      isLoading: statusRef.current === "pending" && dataRef.current === undefined,
      isFetching: false,
      isError: statusRef.current === "error",
      isSuccess: statusRef.current === "success",
      status: statusRef.current,
      refetch: executeFetch,
    };
  }, []);

  useEffect(() => {
    if (enabled) {
      void executeFetch();
    }
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [enabled, keyString, executeFetch]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!isProfileScopedKey(queryKey)) return;

    const handleProfileChange = () => {
      if (enabled) {
        void executeFetch();
      }
    };

    window.addEventListener(PROFILE_CONTEXT_CHANGE_EVENT, handleProfileChange);
    return () => {
      window.removeEventListener(PROFILE_CONTEXT_CHANGE_EVENT, handleProfileChange);
    };
  }, [enabled, queryKey, executeFetch]);

  const isLoading = status === "pending" && data === undefined;
  const isError = status === "error";
  const isSuccess = status === "success";

  return {
    data,
    error,
    isLoading,
    isFetching,
    isError,
    isSuccess,
    status,
    refetch: executeFetch,
  };
}

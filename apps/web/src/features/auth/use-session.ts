import { useQuery } from "@tanstack/react-query";

import {
  ApiClientError,
  apiRequest,
  type SessionResponse,
} from "../../lib/api";

export const sessionQueryKey = ["session"] as const;

export function useSession() {
  return useQuery({
    queryKey: sessionQueryKey,
    queryFn: async () => {
      try {
        return await apiRequest<SessionResponse>("/api/v1/auth/session");
      } catch (error) {
        if (error instanceof ApiClientError && error.status === 401) {
          return null;
        }
        throw error;
      }
    },
  });
}

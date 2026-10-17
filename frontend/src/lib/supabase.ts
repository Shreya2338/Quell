import { createClient } from "@supabase/supabase-js";
import {
  projectId,
  publicAnonKey,
} from "../../utils/supabase/info";

const supabaseUrl = `https://${projectId}.supabase.co`;

export const supabase = createClient(
  supabaseUrl,
  publicAnonKey,
  {
    auth: {
      persistSession: true,
      autoRefreshToken: true,
      detectSessionInUrl: true,
    },
  },
);
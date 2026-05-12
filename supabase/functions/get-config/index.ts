import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Client-Info, Apikey",
};

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { status: 200, headers: corsHeaders });
  }

  // Try both naming conventions, then fall back to the known Railway URL.
  // This ensures the frontend always gets a valid URL even if secrets aren't configured.
  const auditApiUrl =
    Deno.env.get("AUDIT_API_URL") ||
    Deno.env.get("VITE_AUDIT_API_URL") ||
    "https://walkthroughgitrep-production.up.railway.app";

  return new Response(
    JSON.stringify({ audit_api_url: auditApiUrl }),
    {
      headers: {
        ...corsHeaders,
        "Content-Type": "application/json",
      },
    }
  );
});

# Analytics setup

The dashboard is available from the app's **Analytics** sidebar page. It records
random Streamlit session IDs and aggregate processing counts only. It does not
store PDF files, their contents, extracted text, filenames, IP addresses, or
browser fingerprints. Session counts are approximate visits: a reconnect or a
new browser session can count again.

## Supabase

1. Create a Supabase project and run `supabase_analytics.sql` in its SQL Editor.
2. In Streamlit's app secrets, add the project URL, a server-side secret/service
   role key, and a separate password for the analytics page:

   ```toml
   SUPABASE_URL = "https://your-project.supabase.co"
   SUPABASE_SECRET_KEY = "your-server-side-secret-key"
   ANALYTICS_PASSWORD = "choose-a-long-private-password"
   ```

   `SUPABASE_SERVICE_ROLE_KEY` can be used instead of `SUPABASE_SECRET_KEY`.
   Keep this key in Streamlit secrets; never put it in app code or expose it to
   the browser.
3. Restart or redeploy the app. If analytics secrets are absent, PDF processing
   continues and analytics logging stays disabled.

The free Supabase project can pause after inactivity, and free-tier backups are
limited. Export the event table periodically if you need to retain the history.

# Creating the first administrator on Render Free

Render Free services do not provide an interactive shell. This project can create its first administrator during a deployment without using a shell.

1. In Render, open the `it-centre-rms` service and select **Environment** in the left navigation.
2. Add these secret environment variables, using a unique strong password:

   ```text
   DJANGO_BOOTSTRAP_ADMIN_USERNAME=your-admin-username
   DJANGO_BOOTSTRAP_ADMIN_PASSWORD=a-long-unique-password
   DJANGO_BOOTSTRAP_ADMIN_EMAIL=admin@example.com
   ```

3. Ensure the service's **Build Command** runs migrations after installing dependencies, for example:

   ```bash
   pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate
   ```

4. Select **Manual Deploy** then **Deploy latest commit**.
5. After the deployment succeeds, remove all three `DJANGO_BOOTSTRAP_ADMIN_*` variables from Render and save the environment settings.
6. Log in at `/accounts/login/`, then open `/admin-panel/`.

The bootstrap creates an account only when that username does not already exist, so later deployments cannot overwrite its password. Removing the variables after the first deploy keeps the password out of the hosting environment.

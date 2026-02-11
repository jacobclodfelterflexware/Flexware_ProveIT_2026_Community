// API endpoint to get EMQX dashboard token
// This proxies the login to avoid CORS issues and keeps credentials server-side

const EMQX_CREDENTIALS = {
  uncurated: {
    url: process.env.EMQX_UNCURATED_API_URL || 'http://YOUR_MQTT_UNCURATED_HOST:YOUR_EMQX_DASHBOARD_PORT',
    username: process.env.EMQX_UNCURATED_USERNAME || 'admin',
    password: process.env.EMQX_UNCURATED_PASSWORD || 'Fl3xT3ch1!',
  },
  curated: {
    url: process.env.EMQX_CURATED_API_URL || 'http://YOUR_MQTT_CURATED_HOST:YOUR_EMQX_DASHBOARD_PORT',
    username: process.env.EMQX_CURATED_USERNAME || 'admin',
    password: process.env.EMQX_CURATED_PASSWORD || 'Fl3xT3ch1!',
  },
};

export async function GET(request: Request) {
  const url = new URL(request.url);
  const broker = url.searchParams.get('broker') || 'uncurated';

  const creds = broker === 'curated' ? EMQX_CREDENTIALS.curated : EMQX_CREDENTIALS.uncurated;

  try {
    const response = await fetch(`${creds.url}/api/v5/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        username: creds.username,
        password: creds.password,
      }),
    });

    if (!response.ok) {
      const error = await response.json();
      return Response.json(
        { error: error.message || 'Login failed' },
        { status: response.status }
      );
    }

    const data = await response.json();
    return Response.json({
      token: data.token,
      version: data.version,
    });
  } catch (error) {
    console.error('[EMQX Token] Error:', error);
    return Response.json(
      { error: 'Failed to connect to EMQX' },
      { status: 500 }
    );
  }
}

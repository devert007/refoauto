const { authenticate } = require('@google-cloud/local-auth');
const { google } = require('googleapis');
const fs = require('fs');
const path = require('path');

const CREDENTIALS_PATH = process.env.GDRIVE_CREDENTIALS_PATH || './cred.json';
const TOKEN_PATH = path.join(require('os').homedir(), '.gdrive-server', 'token.json');

async function getToken() {
  console.log('Starting OAuth flow...');
  console.log('Credentials path:', CREDENTIALS_PATH);
  console.log('Token will be saved to:', TOKEN_PATH);

  const auth = await authenticate({
    scopes: ['https://www.googleapis.com/auth/drive.readonly'],
    keyfilePath: CREDENTIALS_PATH,
  });

  const tokenDir = path.dirname(TOKEN_PATH);
  if (!fs.existsSync(tokenDir)) {
    fs.mkdirSync(tokenDir, { recursive: true });
  }

  fs.writeFileSync(TOKEN_PATH, JSON.stringify(auth.credentials));
  console.log('\nToken saved to:', TOKEN_PATH);
  console.log('Now restart Claude Code and gdrive should work!');
}

getToken().catch(console.error);

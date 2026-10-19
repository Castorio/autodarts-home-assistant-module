import { HomeAssistantModule } from './HomeAssistantModule.js';

new HomeAssistantModule().start().catch((err) => {
  console.error('Failed to start the Home Assistant module:', err);
  process.exit(1);
});

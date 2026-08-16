import { App, Editor, MarkdownView, Modal, Notice, Plugin, PluginSettingTab, Setting, TFile, TFolder, WorkspaceLeaf } from 'obsidian';
import { ChatView, VIEW_TYPE_CHAT } from './ChatView';

interface LabAgentSettings {
	serverUrl: string;
	username: string;
	chatHistory: { role: string, content: string }[];
	sessionId: string;
	sessions: Record<string, { title: string, updatedAt: number, history: any[] }>;
}

const DEFAULT_SETTINGS: LabAgentSettings = {
	serverUrl: 'http://127.0.0.1:8000',
	username: '张同学',
	chatHistory: [],
	sessionId: '',
	sessions: {}
}

export default class LabAgentPlugin extends Plugin {
	settings: LabAgentSettings;

	async onload() {
		await this.loadSettings();

		// Register the Chat View
		this.registerView(
			VIEW_TYPE_CHAT,
			(leaf) => new ChatView(leaf, this)
		);

		// Ribbon icon to open chat view
		const ribbonIconEl = this.addRibbonIcon('bot', 'Lab AI Copilot', (evt: MouseEvent) => {
			this.activateView();
		});
		ribbonIconEl.addClass('lab-agent-ribbon-class');

		// Command to open chat view
		this.addCommand({
			id: 'open-lab-chat-view',
			name: 'Open Lab AI Copilot',
			callback: () => {
				this.activateView();
			}
		});

		// Command to Sync Vault to Lab Cloud
		this.addCommand({
			id: 'sync-to-lab-cloud',
			name: 'Sync to Lab Cloud',
			callback: async () => {
				await this.syncToLabCloud();
			}
		});

		// Settings tab
		this.addSettingTab(new LabAgentSettingTab(this.app, this));
	}

	onunload() {
		this.app.workspace.detachLeavesOfType(VIEW_TYPE_CHAT);
	}

	async loadSettings() {
		this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
	}

	async saveSettings() {
		await this.saveData(this.settings);
	}

	async activateView() {
		const { workspace } = this.app;
		
		let leaf: WorkspaceLeaf | null = null;
		const leaves = workspace.getLeavesOfType(VIEW_TYPE_CHAT);
		
		if (leaves.length > 0) {
			leaf = leaves[0];
		} else {
			leaf = workspace.getRightLeaf(false);
			await leaf?.setViewState({ type: VIEW_TYPE_CHAT, active: true });
		}
		
		if (leaf) {
			workspace.revealLeaf(leaf);
		}
	}

	async syncToLabCloud() {
		new Notice('Starting sync to Lab Cloud...');
		const allItems = this.app.vault.getAllLoadedFiles();
		const files = allItems.filter(f => f instanceof TFile && f.extension === 'md') as TFile[];
		const folders = allItems.filter(f => f instanceof TFolder && f.path !== '/') as TFolder[];
		
		let successCount = 0;
		let failCount = 0;

		// 1. Sync Folders First
		for (const folder of folders) {
			await this.uploadFolder(folder);
		}

		// 2. Sync Files Concurrently
		const limit = 5;
		let active = 0;
		let index = 0;

		return new Promise<void>((resolve) => {
			const next = async () => {
				if (index >= files.length && active === 0) {
					new Notice(`Sync complete: ${successCount} files succeeded, ${failCount} failed.`);
					resolve();
					return;
				}
				
				while (active < limit && index < files.length) {
					const file = files[index++];
					active++;
					
					this.uploadFile(file).then(success => {
						if (success) successCount++;
						else failCount++;
					}).catch(() => {
						failCount++;
					}).finally(() => {
						active--;
						next();
					});
				}
			};
			next();
		});
	}

	async uploadFolder(folder: TFolder): Promise<boolean> {
		try {
			const response = await fetch(`${this.settings.serverUrl}/api/upload/folder`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					username: this.settings.username,
					foldername: folder.path
				})
			});
			return response.ok;
		} catch (e) {
			return false;
		}
	}

	async uploadFile(file: TFile): Promise<boolean> {
		try {
			const content = await this.app.vault.read(file);
			const payload = {
				username: this.settings.username,
				filename: file.path,
				content: content
			};

			// We use fetch since it's built-in in the Obsidian environment
			const response = await fetch(`${this.settings.serverUrl}/api/upload`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(payload)
			});

			return response.ok;
		} catch (e) {
			console.error(`Failed to upload ${file.name}:`, e);
			return false;
		}
	}
}

class LabAgentSettingTab extends PluginSettingTab {
	plugin: LabAgentPlugin;

	constructor(app: App, plugin: LabAgentPlugin) {
		super(app, plugin);
		this.plugin = plugin;
	}

	display(): void {
		const {containerEl} = this;
		containerEl.empty();

		new Setting(containerEl)
			.setName('Server URL')
			.setDesc('API Endpoint of the agent-service')
			.addText(text => text
				.setPlaceholder('http://127.0.0.1:8000')
				.setValue(this.plugin.settings.serverUrl)
				.onChange(async (value) => {
					this.plugin.settings.serverUrl = value;
					await this.plugin.saveSettings();
				}));
				
		new Setting(containerEl)
			.setName('Username')
			.setDesc('Your identity in the Lab Knowledge Base')
			.addText(text => text
				.setPlaceholder('张同学')
				.setValue(this.plugin.settings.username)
				.onChange(async (value) => {
					this.plugin.settings.username = value;
					await this.plugin.saveSettings();
				}));
	}
}

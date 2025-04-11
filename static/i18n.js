const i18n = {
    en: {
        welcome: {
            title: "Welcome to RCALocal Version",
            subtitle: "Please enter a task prompt to start a new task"
        },
        config: {
            title: "System Configuration",
            subtitle: "Please fill in the necessary configuration information to continue using the system",
            note: "Please ensure that the following configuration information is correct.",
            apiKeyNote: "If you do not have an API key, please obtain one from the corresponding AI service provider.",
            llmConfig: "LLM Configuration",
            serverConfig: "Server Configuration",
            save: "Save Configuration",
            cancel: "Cancel",
            required: "Required"
        },
        input: {
            placeholder: "Enter task prompt...",
            button: "Create Task"
        },
        history: {
            title: "History Tasks"
        },
        status: {
            running: "Task running",
            completed: "Task completed",
            failed: "Task failed",
            error: "Error"
        },
        buttons: {
            configSetting: "Configuration"
        }
    },
};

function getCurrentLanguage() {
    return localStorage.getItem('language') || 'en';
}

function setLanguage(lang) {
    localStorage.setItem('language', lang);
    updatePageContent(lang);
}

function updatePageContent(lang) {
    const texts = i18n[lang];

    updateElementText('.welcome-message h2', texts.welcome.title);
    updateElementText('.welcome-message p', texts.welcome.subtitle);

    updateElementText('#config-button', texts.buttons.configSetting);
    if (document.getElementById('config-button')) {
        document.getElementById('config-button').title = texts.buttons.configSetting;
    }

    updateElementText('.config-modal-header h2', texts.config.title);
    updateElementText('.config-modal-header p', texts.config.subtitle);
    updateElementText('.note-box p:first-child', texts.config.note);
    updateElementText('.note-box p:last-child', texts.config.apiKeyNote);

    const configSections = document.querySelectorAll('.config-section h3');
    if (configSections) {
        configSections.forEach(h3 => {
            if (h3.textContent && h3.textContent.includes('LLM')) {
                h3.textContent = texts.config.llmConfig;
            } else if (h3.textContent && h3.textContent.includes('Server')) {
                h3.textContent = texts.config.serverConfig;
            }
        });
    }

    updateElementText('#save-config-btn', texts.config.save);
    updateElementText('#cancel-config-btn', texts.config.cancel);

    updateElementText('#prompt-input', texts.input.placeholder, 'placeholder');
    updateElementText('button[onclick="createTask()"]', texts.input.button);

    updateElementText('.history-panel h3', texts.history ? texts.history.title : 'History Tasks');

    const requiredMarks = document.querySelectorAll('.required-mark');
    if (requiredMarks) {
        requiredMarks.forEach(mark => {
            mark.textContent = texts.config.required;
        });
    }
}

function updateElementText(selector, text, attribute = 'textContent') {
    try {
        const element = document.querySelector(selector);
        if (element && text) {
            if (attribute === 'placeholder') {
                element.placeholder = text;
            } else {
                element[attribute] = text;
            }
        }
    } catch (e) {
        console.warn(`Failed to update text for selector "${selector}":`, e);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const currentLang = getCurrentLanguage();
    document.getElementById('language-select').value = currentLang;
    updatePageContent(currentLang);

    document.getElementById('language-select').addEventListener('change', (e) => {
        setLanguage(e.target.value);
    });
});

document.addEventListener('DOMContentLoaded', () => {
    const healthProblemInput = document.getElementById('healthProblem');
    const diagnoseButton = document.getElementById('diagnoseBtn');
    const buttonText = diagnoseButton.querySelector('.button-text');
    const spinner = diagnoseButton.querySelector('.spinner');

    const voiceInputBtn = document.getElementById('voiceInputBtn');
    const clearInputBtn = document.getElementById('clearInputBtn');
    const imageUpload = document.getElementById('imageUpload');
    const imagePreview = document.getElementById('imagePreview');
    const previewImage = document.getElementById('previewImage');
    const removeImageBtn = document.getElementById('removeImageBtn');

    const severitySpan = document.getElementById('severity');
    const adviceDiv = document.getElementById('advice');
    const disclaimerSpan = document.getElementById('disclaimer');
    const resultsBox = document.getElementById('results');

    // Speech Recognition setup
    let recognition;
    let isRecording = false;

    // Initially hide the results box
    resultsBox.style.display = 'none';

    // --- Event Listeners ---

    diagnoseButton.addEventListener('click', async () => {
        const problem = healthProblemInput.value.trim();
        const imageFile = imageUpload.files[0];

        if (problem === '' && !imageFile) {
            alert('Please describe your health problem or upload an image before clicking "Get AI Advice".');
            return;
        }

        // Show loading state
        buttonText.textContent = 'Analyzing...';
        spinner.style.display = 'inline-block';
        diagnoseButton.disabled = true;

        severitySpan.textContent = 'Processing...';
        adviceDiv.innerHTML = '<p>HealGenie is carefully analyzing your input. This may take a moment.</p>';
        disclaimerSpan.textContent = '';
        resultsBox.style.display = 'block';

        // Reset severity indicator styles
        const severityIndicator = severitySpan.parentElement;
        severityIndicator.removeAttribute('severity');
        severityIndicator.classList.remove('severity-indicator'); // Remove to clear previous background


        try {
            const formData = new FormData();
            formData.append('problem', problem);
            if (imageFile) {
                formData.append('image', imageFile);
            }

            const response = await fetch('/diagnose', {
                method: 'POST',
                body: formData // No Content-Type header needed for FormData; browser sets it
            });

            const data = await response.json();

            // Update the UI with AI's response
            severitySpan.textContent = data.severity;
            adviceDiv.innerHTML = formatMarkdownToHtml(data.advice); // Use new markdown formatter
            disclaimerSpan.textContent = data.disclaimer;

            // Apply color based on severity
            severityIndicator.classList.add('severity-indicator'); // Re-add class
            severityIndicator.setAttribute('severity', data.severity);


        } catch (error) {
            console.error('Error fetching diagnosis:', error);
            severitySpan.textContent = 'Error';
            adviceDiv.innerHTML = '<p>An error occurred while getting advice. Please try again.</p>';
            disclaimerSpan.textContent = 'Please note: This system is for informational purposes only.';
            const severityIndicator = severitySpan.parentElement;
            severityIndicator.classList.add('severity-indicator'); // Re-add class for error state
            severityIndicator.setAttribute('severity', 'Error'); // Set severity to Error for gray color
        } finally {
            buttonText.textContent = 'Get AI Advice';
            spinner.style.display = 'none';
            diagnoseButton.disabled = false;
        }
    });

    // Image Upload Logic
    imageUpload.addEventListener('change', (event) => {
        const file = event.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = (e) => {
                previewImage.src = e.target.result;
                imagePreview.style.display = 'block';
            };
            reader.readAsDataURL(file);
        } else {
            imagePreview.style.display = 'none';
            previewImage.src = '#';
        }
    });

    removeImageBtn.addEventListener('click', () => {
        imageUpload.value = ''; // Clear the file input
        imagePreview.style.display = 'none';
        previewImage.src = '#';
    });

    clearInputBtn.addEventListener('click', () => {
        healthProblemInput.value = '';
        imageUpload.value = '';
        imagePreview.style.display = 'none';
        previewImage.src = '#';
        resultsBox.style.display = 'none'; // Hide results after clearing
    });


    // --- Voice Input Logic (Web Speech API) ---
    voiceInputBtn.addEventListener('click', () => {
        if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
            alert('Your browser does not support Web Speech API. Please use a modern browser like Chrome or Edge.');
            return;
        }

        if (isRecording) {
            recognition.stop();
            return;
        }

        recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
        recognition.lang = 'en-US';
        recognition.interimResults = true; // Show interim results
        recognition.continuous = false; // Stop after a single utterance

        recognition.onstart = () => {
            isRecording = true;
            voiceInputBtn.classList.add('recording');
            voiceInputBtn.title = 'Stop Recording';
            console.log('Voice recording started...');
        };

        recognition.onresult = (event) => {
            let interimTranscript = '';
            let finalTranscript = '';

            for (let i = event.resultIndex; i < event.results.length; ++i) {
                if (event.results[i].isFinal) {
                    finalTranscript += event.results[i][0].transcript;
                } else {
                    interimTranscript += event.results[i][0].transcript;
                }
            }
            healthProblemInput.value = finalTranscript + interimTranscript; // Update textarea with results
        };

        recognition.onerror = (event) => {
            console.error('Speech recognition error:', event.error);
            isRecording = false;
            voiceInputBtn.classList.remove('recording');
            voiceInputBtn.title = 'Speak your symptoms';
            alert('Error during voice input: ' + event.error);
        };

        recognition.onend = () => {
            isRecording = false;
            voiceInputBtn.classList.remove('recording');
            voiceInputBtn.title = 'Speak your symptoms';
            console.log('Voice recording ended.');
        };

        recognition.start();
    });

    // --- Helper function to format AI advice (Markdown to HTML) ---
    function formatMarkdownToHtml(markdownText) {
        if (!markdownText) return '';

        // Basic Markdown to HTML conversion
        let html = markdownText
            .replace(/### (.*)/g, '<h3>$1</h3>') // H3 headings
            .replace(/## (.*)/g, '<h2>$1</h2>') // H2 headings
            .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>') // Bold text
            .replace(/\* ([^*]+)/g, '<li>$1</li>'); // Unordered list items (simple)

        // Convert consecutive list items into an actual <ul>
        // This is a simple approach, can be more robust with a full Markdown parser if needed
        let inList = false;
        html = html.split('\n').map(line => {
            if (line.startsWith('<li>') && !inList) {
                inList = true;
                return `<ul>${line}`;
            } else if (!line.startsWith('<li>') && inList) {
                inList = false;
                return `</ul>${line}`;
            }
            return line;
        }).join('\n');
        if (inList) html += '</ul>'; // Close list if it ends abruptly

        // Convert double newlines to paragraphs for non-list content
        html = html.split('\n\n').map(p => {
            if (!p.startsWith('<h') && !p.startsWith('<ul') && !p.startsWith('<li')) {
                 return `<p>${p.replace(/\n/g, '<br>')}</p>`;
            }
            return p;
        }).join('');

        return html;
    }
});
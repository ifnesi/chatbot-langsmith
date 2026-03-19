// Chat Application JavaScript
$(document).ready(function() {
    const messagesContainer = $('#messagesContainer');
    const chatForm = $('#chatForm');
    const messageInput = $('#messageInput');
    const sendBtn = $('#sendBtn');
    const resetBtn = $('#resetBtn');
    const quickQuestions = $('.quick-q');

    // Auto-focus on input
    messageInput.focus();

    // Handle form submission
    chatForm.on('submit', function(e) {
        e.preventDefault();
        const question = messageInput.val().trim();

        if (question) {
            sendMessage(question);
            messageInput.val('');
            hideQuickQuestions();
        }
    });

    // Handle quick question clicks
    quickQuestions.on('click', function() {
        const question = $(this).data('question');
        sendMessage(question);
        hideQuickQuestions();
    });

    // Handle reset button
    resetBtn.on('click', function() {
        if (confirm('Are you sure you want to clear the conversation history?')) {
            resetConversation();
        }
    });

    // Hide quick questions after first message
    function hideQuickQuestions() {
        if ($('#quickQuestions').is(':visible')) {
            $('#quickQuestions').fadeOut(300);
        }
    }

    // Hide empty state when first message is added
    function hideEmptyState() {
        const emptyState = $('#emptyState');
        if (emptyState.length && emptyState.is(':visible')) {
            emptyState.fadeOut(400, function() {
                $(this).remove();
            });
        }
    }

    // Show empty state when messages are cleared
    function showEmptyState() {
        if (!$('#emptyState').length) {
            const emptyStateHtml = `
                <div class="empty-state" id="emptyState">
                    <div class="text-center py-5">
                        <div class="empty-icon mb-4">
                            <i class="bi bi-chat-dots-fill text-primary"></i>
                        </div>
                        <h3 class="text-light mb-3">Welcome to CloudSync Pro Support!</h3>
                        <p class="text-muted mb-4">Ask me anything about CloudSync Pro features, pricing, or troubleshooting.</p>
                        <div class="feature-grid">
                            <div class="feature-item">
                                <i class="bi bi-lightning-charge-fill text-warning"></i>
                                <span>Instant Answers</span>
                            </div>
                            <div class="feature-item">
                                <i class="bi bi-shield-check text-success"></i>
                                <span>24/7 Available</span>
                            </div>
                            <div class="feature-item">
                                <i class="bi bi-robot text-primary"></i>
                                <span>AI-Powered</span>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            messagesContainer.prepend(emptyStateHtml);
        }
    }

    // Send message to chatbot
    function sendMessage(question) {
        // Disable input while processing
        messageInput.prop('disabled', true);
        sendBtn.prop('disabled', true);

        // Add user message to chat
        addMessage(question, 'user');

        // Add loading indicator
        const loadingMsg = addLoadingMessage();

        // Make AJAX request
        $.ajax({
            url: '/api/chat',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ question: question }),
            success: function(response) {
                // Remove loading indicator
                loadingMsg.remove();

                if (response.success) {
                    // Add bot response
                    addMessage(response.answer, 'bot', response.sources);
                } else {
                    addErrorMessage('Sorry, something went wrong. Please try again.');
                }
            },
            error: function(xhr) {
                // Remove loading indicator
                loadingMsg.remove();

                let errorMsg = 'Sorry, I encountered an error. Please try again.';
                if (xhr.responseJSON && xhr.responseJSON.error) {
                    errorMsg = xhr.responseJSON.error;
                }
                addErrorMessage(errorMsg);
            },
            complete: function() {
                // Re-enable input
                messageInput.prop('disabled', false);
                sendBtn.prop('disabled', false);
                messageInput.focus();
            }
        });
    }

    // Add message to chat
    function addMessage(content, type, sources = null) {
        // Hide empty state on first message
        hideEmptyState();

        const time = new Date().toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit'
        });

        const messageClass = type === 'user' ? 'user-message' : 'bot-message';
        const icon = type === 'user' ?
            '<i class="bi bi-person-fill me-2"></i>' :
            '<i class="bi bi-robot me-2"></i>';

        // Only escape user input for XSS protection
        // Bot responses are trusted and may contain HTML formatting
        const messageContent = type === 'user' ? escapeHtml(content) : content;

        let messageHtml = `
            <div class="message-bubble ${messageClass}">
                <div>${icon}${messageContent}</div>
                <small class="message-time">${time}</small>
        `;

        // Add sources if present
        if (sources && sources.length > 0) {
            messageHtml += `
                <div class="sources-container">
                    <small class="d-block mb-2">
                        <i class="bi bi-files me-1"></i>Sources consulted:
                    </small>
            `;

            sources.forEach((source, index) => {
                const sourceId = source.source.replace('Redis ', '');
                const preview = source.content || 'No preview available';

                messageHtml += `
                    <div class="source-item mb-2 collapsed" data-source-id="${index}">
                        <div class="source-header">
                            <span class="source-badge">#${index + 1}</span>
                            <small class="text-muted source-id">${sourceId}</small>
                            <i class="bi bi-chevron-down ms-2 source-toggle"></i>
                        </div>
                        <div class="source-preview mt-2" style="display: none;">
                            <small>${escapeHtml(preview)}</small>
                        </div>
                    </div>
                `;
            });

            messageHtml += `</div>`;
        }

        messageHtml += `</div>`;

        messagesContainer.append(messageHtml);

        // Add click handlers for expandable sources
        messagesContainer.find('.source-item').last().parent().find('.source-item').on('click', function() {
            toggleSource($(this));
        });

        scrollToBottom();
    }

    // Toggle source expansion
    function toggleSource($sourceItem) {
        const $preview = $sourceItem.find('.source-preview');
        const $toggle = $sourceItem.find('.source-toggle');

        if ($sourceItem.hasClass('collapsed')) {
            // Expand
            $sourceItem.removeClass('collapsed').addClass('expanded');
            $preview.slideDown(200);
            $toggle.removeClass('bi-chevron-down').addClass('bi-chevron-up');
        } else {
            // Collapse
            $sourceItem.removeClass('expanded').addClass('collapsed');
            $preview.slideUp(200);
            $toggle.removeClass('bi-chevron-up').addClass('bi-chevron-down');
        }
    }

    // Add loading message
    function addLoadingMessage() {
        const loadingHtml = $('#loadingTemplate').html();
        messagesContainer.append(loadingHtml);
        scrollToBottom();
        return messagesContainer.find('.loading-message').last();
    }

    // Add error message
    function addErrorMessage(message) {
        const time = new Date().toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit'
        });

        const errorHtml = `
            <div class="message-bubble bot-message" style="border-color: #f85149;">
                <div>
                    <i class="bi bi-exclamation-triangle-fill text-danger me-2"></i>
                    ${escapeHtml(message)}
                </div>
                <small class="message-time">${time}</small>
            </div>
        `;

        messagesContainer.append(errorHtml);
        scrollToBottom();
    }

    // Reset conversation
    function resetConversation() {
        $.ajax({
            url: '/api/reset',
            method: 'POST',
            contentType: 'application/json',
            success: function(response) {
                if (response.success) {
                    // Clear messages
                    messagesContainer.empty();

                    // Show empty state again
                    showEmptyState();

                    // Show quick questions again if they were hidden
                    if (!$('#quickQuestions').is(':visible')) {
                        $('#quickQuestions').fadeIn(300);
                    }

                    // Show success message
                    const successHtml = `
                        <div class="alert alert-success alert-dismissible fade show mt-3" role="alert">
                            <i class="bi bi-check-circle-fill me-2"></i>
                            Conversation history cleared!
                            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                        </div>
                    `;
                    messagesContainer.append(successHtml);

                    // Remove success message after 3 seconds
                    setTimeout(function() {
                        messagesContainer.find('.alert').fadeOut(300, function() {
                            $(this).remove();
                        });
                    }, 3000);
                }
            },
            error: function() {
                alert('Failed to reset conversation. Please try again.');
            }
        });
    }

    // Scroll to bottom of messages
    function scrollToBottom() {
        messagesContainer.animate({
            scrollTop: messagesContainer[0].scrollHeight
        }, 300);
    }

    // Escape HTML to prevent XSS
    function escapeHtml(text) {
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.replace(/[&<>"']/g, function(m) { return map[m]; });
    }

    // Handle Enter key (Shift+Enter for new line)
    messageInput.on('keypress', function(e) {
        if (e.which === 13 && !e.shiftKey) {
            e.preventDefault();
            chatForm.submit();
        }
    });
});

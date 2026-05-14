var onSite = function(){
	"use strict"
    
    var handleDropdownSelect = function(){
		document.addEventListener("click", function (e) {
            const dropdownMenus = document.querySelectorAll('.on-dropdown-menu');
            if (!e.target.closest(".dropdown-slt")) {
                dropdownMenus.forEach((item) => {
                    item.style.display = "none";
                })
            }
        });
        jQuery('.on-dropdown-input').on('focus',function(){
            jQuery(jQuery(this).attr('data-dropdown-target')).show();
        })
        jQuery('.on-dropdown-item').on('click',function(){
            $(this).closest('.dropdown-slt').find('.on-dropdown-input').val($(this).attr('data-val'));
            $(this).closest('.dropdown-slt').find('.on-dropdown-menu').hide();
        })
        jQuery(document).on('focus','.on-dropdown-name-input',function(){
            jQuery(jQuery(this).attr('data-dropdown-target')).show();
        })
        jQuery(document).on('click','.on-dropdown-item',function(){
            $(this).closest('.dropdown-slt').find('.on-dropdown-id-input').val($(this).data('id'));
            $(this).closest('.dropdown-slt').find('.on-dropdown-name-input').val($(this).data('name'));
            $(this).closest('.dropdown-slt').find('.on-dropdown-menu').hide();
        })
	}

    var handleBankDetails = function(){
        // alert(!$('.AccountInput').val());
        if (!$('.AccountInput').val()) {
            $('.AccountInput').closest('.dropdown-slt').find('.bank-detail').hide();
        }else{
            $('.AccountInput').closest('.dropdown-slt').find('.bank-detail').show();
        }  
            
        $('.on-dropdown-item').on('click',function (e) {
           
            if ($('.AccountInput').length > 0) {
                $('.AccountInput').closest('.dropdown-slt').find('.bank-detail').show();
                $('.AccountInput').hide();
            }
        });

        $('.remove-input-btn').click(function () {
            if ($('.AccountInput').length > 0) {
                $('.AccountInput').show();
            }
        });
        
        $('.add-input-btn').click(function (e) {
            if ($('.bank-detail').length > 0) {
                $('.bank-detail').hide();
            }
        });

	}

    var handleAddInput = function(){
        $('.add-input-btn').click(function (e) {
            e.preventDefault(); 
            $(this).closest('.add-input-box').find('.input-content').show();
            $(this).hide();
        });
    
        $('.remove-input-btn').click(function () {
            $(this).closest('.add-input-box').find('.input-content').hide();
            $(this).closest('.add-input-box').find('.add-input-btn').show();
        });
    }

    var handleModalCloseOffcanvas = function () {
        const offcanvasElements = document.querySelectorAll('.TriggerOffcanvas');
        const modalElements = document.querySelectorAll('.TriggerModal');

        offcanvasElements.forEach(offcanvas => {
            offcanvas.addEventListener('show.bs.offcanvas', event => {
                // Remove all modal backdrops
                document.querySelectorAll('.modal-backdrop').forEach(b => b.remove());

                // Hide all modals using Bootstrap API or fallback
                modalElements.forEach(modal => {
                    const bsModal = bootstrap.Modal.getInstance(modal);
                    if (bsModal) {
                        bsModal.hide();
                    } else {
                        modal.classList.remove('show');
                        modal.setAttribute('aria-hidden', 'true');
                        modal.style.display = 'none';
                    }
                });

                // Reset body scroll state
                document.body.classList.remove('modal-open');
                document.body.style.overflow = null;
                document.body.style.paddingRight = null;
            });
        });
    };

    var handleQuotationTbl = function(){
        document.querySelectorAll("#quatationTbl tbody tr").forEach(row => {
            row.addEventListener("click", function (e) {
            const lastTd = this.querySelector("td:last-child");
            
            // If clicked inside the last td (status or 3-dot menu), don't trigger the offcanvas
            if (lastTd.contains(e.target)) {
                return;
            }

            // Manually trigger the offcanvas
            const targetSelector = this.getAttribute("data-bs-target");
            if (targetSelector) {
                const offcanvasElement = document.querySelector(targetSelector);
                if (offcanvasElement) {
                const bsOffcanvas = new bootstrap.Offcanvas(offcanvasElement);
                bsOffcanvas.show();
                }
            }
            });

            // Remove default data-bs-toggle to prevent auto activation
            row.removeAttribute("data-bs-toggle");
        });
    }

    var handleQuotationsectionRow = function(){
        const parentRows = document.querySelectorAll(".parent-row");
        parentRows.forEach((parentRow) => {
            parentRow.addEventListener("click", (event) => {
            
            // Prevent toggling if clicked on action button or anything inside last cell
            const lastCell = parentRow.querySelector("td:last-child");
            if (lastCell.contains(event.target)) {
                return; // Do nothing
            }
            
            // Prevent toggling if clicked inside any .section-utility
            const utilityElements = parentRow.querySelectorAll(".section-utility");
            for (const element of utilityElements) {
                if (element.contains(event.target)) return;
            }

            parentRow.classList.toggle("expanded");

            let next = parentRow.nextElementSibling;
            while (next && next.classList.contains("child-row")) {
                next.style.display =
                next.style.display === "table-row" ? "none" : "table-row";
                next = next.nextElementSibling;
            }
            });
        });
    }

    var handlepreTaxDeductionInputCheck = function(){
        const rows = document.querySelectorAll('.amount-row');
		rows.forEach(row => {
			const input = row.querySelector('.amount-input');
			const checkbox = row.querySelector('.controlled-checkbox');
			if (!input || !checkbox) {
				return;
			}

			input.addEventListener('input', function () {
			const value = parseFloat(this.value);
			checkbox.checked = value > 0;
			});
		});
    }

    var handlecheckedDropdownSelect = function () {
        const toggle = document.getElementById('toggleDropdown');
        if (toggle) {
            toggle.addEventListener('change', function () {
                document.querySelectorAll('.dropdown-container').forEach(container => {
                    container.classList.toggle('d-none', !this.checked);
                });
            });
        } else {
            // console.warn('Element with ID #toggleDropdown not found.');
        }
    };

    var handleImgOnChange = function () {
        let $currentBox = null;

        $(".img-input-onchange").on('change', function () {
            var input = this;
            var $parentBox = $(input).closest('.img-parent-box');
            var file = input.files[0];

            if (file) {
                var reader = new FileReader();
                reader.onload = function (e) {
                    $parentBox.find('.img-for-onchange')
                        .attr('src', e.target.result)
                        .css('display', 'block');

                    $parentBox.find('.upload-label').hide();
                    $parentBox.find('.cancel-img-btn').show();
                };
                reader.readAsDataURL(file);
            }
        });

        // Show modal and preview image
        $(".cancel-img-btn").on('click', function () {
            $currentBox = $(this).closest('.img-parent-box');
            var imgSrc = $currentBox.find('.img-for-onchange').attr('src');
            $("#previewImageInModal").attr('src', imgSrc);
            const modal = new bootstrap.Modal(document.getElementById('imageRemoveConfirmModal'));
            modal.show();
        });

        // Confirm remove
        $("#confirmRemoveImageBtn").on('click', function () {
            if ($currentBox) {
                $currentBox.find('.img-for-onchange').attr('src', '').hide();
                $currentBox.find('.upload-label').show();
                $currentBox.find('.img-input-onchange').val('');
                $currentBox.find('.cancel-img-btn').hide();

                $currentBox = null;

                
                const modal = bootstrap.Modal.getInstance(document.getElementById('imageRemoveConfirmModal'));
                modal.hide();

                // ✅ Toastr success message
                toastr.options = {
                    "closeButton": true,
                    "positionClass": "toast-top-left",
                    "timeOut": "3000"
                };
                toastr.success("Image removed successfully.", "Success");
            }
        });
    };

    var handleTimeSheetTbl = function(){
        $(document).ready(function () {
            $('#TimeSheettbl tbody tr').on('click', function (e) {
                const lastTd = this.querySelector('td:last-child');

                // If clicked inside the last td (Action column), do nothing
                if (lastTd && lastTd.contains(e.target)) {
                    return;
                }

                // Redirect to detail page
                window.location.href = 'construction/timesheet-detail.html';
            });
        });
    }

    var handleTimeSheetlist = function(){
        $(document).ready(function () {
            $('.timesheet-li').on('click', function () {
                $('.timesheet-li').removeClass('active'); // Remove from all
                $(this).addClass('active'); // Add to clicked one
            });
        });
    }

    var TimeSheetlistfiltering = function(){
        $(document).ready(function () {
            // Toggle from search bar to filter options
            $('.icon-filter, .filter-btn').on('click', function () {
                $('.seach-bar').fadeOut(200, function () {
                    $('.filter-op').fadeIn(200).css('display', 'flex'); // ensure flex layout
                });
            });

            // Toggle back from filter options to search bar
            $('.icon-search, .search-btn').on('click', function () {
                $('.filter-op').fadeOut(200, function () {
                    $('.seach-bar').fadeIn(200).css('display', 'flex'); // ensure flex layout
                });
            });
        });
    }

    var handleMOMTbl = function(){
        $(document).ready(function () {
            $('#MOMtbl tbody tr').on('click', function (e) {
                const lastTd = this.querySelector('td:last-child');

                // If clicked inside the last td (Action column), do nothing
                if (lastTd && lastTd.contains(e.target)) {
                    return;
                }

                // Redirect to detail page
                window.location.href = 'construction/mom-detail.html';
            });
        });
    }

    var handleMOMAtendees = function(){
        $('#attendeeList .on-dropdown-item, #memberList .on-dropdown-item').on('click', function () {
            const selectedName = $(this).find('.attendee-name').text().trim();
            const dropdown = $(this).closest('.dropdown-slt');
            const selectedId = $(this).attr('data-id');
            
            // Decide container based on parent list
            let selectedContainer;
            if ($(this).closest('#attendeeList').length) {
                selectedContainer = $('#attendeeSelected');
            } else {
                selectedContainer = $('#memberSelected');
            }

            // Check if this attendee already exists (by name)
            let alreadyExists = false;
            selectedContainer.find('.attendee-name').each(function () {
                if ($(this).text().trim() === selectedName) {
                    alreadyExists = true;
                    return false; // Break loop
                }
            });

            if (alreadyExists) {
                alert('This attendee has already been selected!');
            } else {
                const input = document.createElement('input');
                input.type = 'hidden';
                input.value = selectedId;
                input.classList.add('attendee-hidden-id');
                input.setAttribute('data-id', selectedId);
                dropdown.append(input);

                // Create attendee tag HTML
                const attendeeTag = `
                <div class="attendee-item d-flex justify-content-between align-items-center py-2 px-3 mb-2 rounded border bg-light" data-id="${selectedId}">
                    <div class="fw-semibold attendee-name">${selectedName}</div>
                    <button type="button" class="btn-close btn-sm remove-attendee" aria-label="Remove"></button>
                </div>
                `;

                // Append the badge to the selected-attendees container
                selectedContainer.append(attendeeTag);
            }

            // CLEAR input value so it stays empty
            setTimeout(function () {
                dropdown.find('.on-dropdown-input').val('');
            }, 0);

            // dropdown.find('.on-dropdown-input').val('');

            // Hide dropdown menu
            dropdown.find('.on-dropdown-menu').hide();
        });

        // Allow removal of attendee badges
        $(document).on('click', '.remove-attendee', function () {
            const badge = $(this).closest('.attendee-item');
            const idToRemove = badge.attr('data-id');

            // Find and remove the matching input
            $('.attendee-hidden-id[data-id="' + idToRemove + '"]').remove();

            badge.remove(); // remove the visual attendee
        });
    }

    var handletodoCategorycolor = function(){
        const colorInput = document.getElementById('newCategoryColor');
        const colorValue = document.getElementById('newCategoryColorValue');
        if (colorInput && colorValue) {
            colorValue.textContent = colorInput.value;
            colorInput.addEventListener('input', function () {
                colorValue.textContent = this.value;
            });
        }
    }

    var handleToDoTbl = function(){
        $(document).ready(function () {
            $('#TODOtbl tbody tr').on('click', function (e) {
                const lastTd = this.querySelector('td:last-child');

                // If clicked inside the last td (Action column), do nothing
                if (lastTd && lastTd.contains(e.target)) {
                    return;
                }

                // Redirect to detail page
                window.location.href = 'construction/todo-detail.html';
            });
        });
    }

    var handleToDoStatusToggle = function(){
        $(document).ready(function () {
            $('.status-toggle').on('click', function () {
                const $this = $(this);
                const $siblings = $this.siblings('.status-toggle');

                $this.fadeOut(200, function () {
                    $this.css('display', 'none'); // ensure it's hidden after fade
                    $siblings.fadeIn(200).css('display', 'inline-block'); // show sibling with fade
                });
            });
        });
    }

    var handleTransactionTbl = function(){
        $('#transactiontbl tbody').on('click', 'tr td:not(:last-child)', function (e) {
            const $td = $(this);
            const $tr = $td.closest('tr');
            const targetOffcanvas = $tr.data('bs-target'); // or data('bs-toggle'), depending on your attribute
            if (targetOffcanvas) {
                const offcanvas = new bootstrap.Offcanvas(targetOffcanvas);
                offcanvas.show();
            }
        });
    }

    var handleBillToShipTo = function(){
        $(document).ready(function () {
			$('.on-dropdown-item').on('click', function () {
				const selectedVal = $(this).data('val');
				const $dropdown = $(this).closest('.dropdown-slt');
				const $input = $dropdown.find('.on-dropdown-input');
				const $address = $dropdown.siblings('.address');

				// Set value
				$input.val(selectedVal);

				// Show address block
				$address.show();

				// Hide dropdown
				$dropdown.find('.on-dropdown-menu').hide();
			});

			$('.remove-btn').on('click', function () {
				const $address = $(this).closest('.address');
				const $dropdown = $address.siblings('.dropdown-slt');
				const $input = $dropdown.find('.on-dropdown-input');

				$input.val('');
				$address.hide();
				$dropdown.find('.on-dropdown-menu').show();

			});
		});
    }

    var handlereferralcoinanimation = function(){
        jQuery(document).ready(function($) {
            let rotation = 0; // start angle

            function flipCoin() {
                rotation += 180; // rotate only 180° each time
                $('#coin').css('transform', 'rotateY(' + rotation + 'deg)');
            }

            // flip every 5 seconds
            setInterval(flipCoin, 5000);

            // first flip
            flipCoin();
        });
    }

    var handleDeleteItem = function () {
        $(document).on('click', '.delete-btn', function () {
            $(this).closest('div').remove(); 
        });
    }

    var handleProjectTbl = function(){
        document.querySelectorAll("#ProjectTbl tbody tr").forEach(row => {
            row.addEventListener("click", function (e) {
                const lastTd = this.querySelector("td:last-child");

                // If clicked inside the last td (action dropdown), stop redirect
                if (lastTd.contains(e.target)) {
                    return;
                }

                // ✅ Redirect to construction/transaction.html
                window.location.href = "construction/transaction.html";
            });
        });
    }

    var handleNewProject = function () {
        const toastTrigger = document.getElementById('create-project-success');
		const toastLiveExample = document.getElementById('liveToast');

		if (toastTrigger) {
			const toastBootstrap = bootstrap.Toast.getOrCreateInstance(toastLiveExample);

			toastTrigger.addEventListener('click', () => {
				// Show toast
				toastBootstrap.show();

				// Hide modal (Bootstrap way, not just removing class)
				const modalEl = document.getElementById('new-project-team');
				const modal = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
				modal.hide();
			});
		}
    }


    /* Function ============ */
	return {
		init:function(){
            handleDropdownSelect();
            handleAddInput();
            handleModalCloseOffcanvas();
            handleQuotationTbl();
            handleBankDetails();
            handleQuotationsectionRow();
            handlepreTaxDeductionInputCheck();
            handlecheckedDropdownSelect();
            handleImgOnChange();
            handleTimeSheetTbl();
            handleTimeSheetlist();
            TimeSheetlistfiltering();
            handleMOMTbl();
            handleMOMAtendees();
            handletodoCategorycolor();
            handleToDoTbl();
            handleToDoStatusToggle();
            handleTransactionTbl();
            handleBillToShipTo();
            handlereferralcoinanimation();
            handleDeleteItem();
            handleProjectTbl();
            handleNewProject();
		},
		
		load:function(){
            
		},
		
		resize:function(){

		},
	}

}

jQuery(document).ready(function() {
	onSite().init();
});
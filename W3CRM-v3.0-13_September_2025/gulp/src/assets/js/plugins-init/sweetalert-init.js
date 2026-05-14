"use strict"
document.querySelector(".btn-sweet-success").onclick = function () {
	Swal.fire({
		title: "Icon success",
		icon: "success",
		confirmButtonText: "Ok, got it!",
		customClass: {
            confirmButton: "btn btn-primary"
        }
	});
}
document.querySelector(".btn-sweet-error").onclick = function () {
	Swal.fire({
		title: "Icon Error",
		icon: "error",
		confirmButtonText: "Ok, got it!",
		customClass: {
            confirmButton: "btn btn-primary"
        }
	});
}
document.querySelector(".btn-sweet-warning").onclick = function () {
	Swal.fire({
		title: "Icon Warning",
		icon: "warning",
		confirmButtonText: "Ok, got it!",
		customClass: {
            confirmButton: "btn btn-primary"
        }
	});
}
document.querySelector(".btn-sweet-info").onclick = function () {
	Swal.fire({
		title: "Icon Info",
		icon: "info",
		confirmButtonText: "Ok, got it!",
		customClass: {
            confirmButton: "btn btn-primary"
        }
	});
}
document.querySelector(".btn-sweet-question").onclick = function () {
	Swal.fire({
		title: "Icon Question",
		icon: "question",
		confirmButtonText: "Ok, got it!",
		customClass: {
            confirmButton: "btn btn-primary"
        }
	});
}

document.querySelector(".btn-sweet-basic").onclick = function () {
	Swal.fire({
		title: "SweetAlert2 is working!",
		confirmButtonText: "Ok, got it!",
		customClass: {
			confirmButton: "btn btn-primary"
		}
	})
}
document.querySelector(".btn-sweet-text").onclick = function () {
	Swal.fire({
		title: "The Internet?",
		text: "That thing is still around?",
		icon: "question",
		confirmButtonText: "Ok, got it!",
		customClass: {
            confirmButton: "btn btn-primary"
        }
	});
}
document.querySelector(".btn-sweet-footer").onclick = function () {
	Swal.fire({
		icon: "error",
		title: "Oops...",
		text: "Something went wrong!",
		footer: '<a href="#">Why do I have this issue?</a>',
		confirmButtonText: "Ok, got it!",
		customClass: {
            confirmButton: "btn btn-primary",
        },
	});
}

document.querySelector(".btn-sweet-tall").onclick = function () {
	Swal.fire({
		imageUrl: "assets/images/tell-modal.jpg",
		imageHeight: 600,
		imageAlt: "A tall image",
		confirmButtonText: "Ok, got it!",
		customClass: {
            confirmButton: "btn btn-primary",
        },
	});
}
document.querySelector(".btn-sweet-image").onclick = function () {
	Swal.fire({
		title: "Sweet!",
		text: "Modal with a custom image.",
		imageUrl: "assets/images/sweet-image.jpg",
		imageWidth: 200,
		imageHeight: 200,
		imageAlt: "Custom image",
		confirmButtonText: "Ok, got it!",
		customClass: {
            confirmButton: "btn btn-primary",
        },
	});
}

document.querySelector(".btn-sweet-draggable").onclick = function () {
	Swal.fire({
		title: "Drag me!",
		icon: "success",
		draggable: true,
		confirmButtonText: "Ok, got it!",
		customClass: {
            confirmButton: "btn btn-primary",
        },
	});
}
document.querySelector(".btn-sweet-custom").onclick = function () {
	Swal.fire({
		title: "<strong>HTML <u>example</u></strong>",
		icon: "info",
		html: `You can use <b>bold text</b>, <a href="#" autofocus>links</a>, and other HTML tags`,
		showCloseButton: true,
		showCancelButton: true,
		focusConfirm: false,
		confirmButtonText: `<i class="fa fa-thumbs-up"></i> Great!`,
		confirmButtonAriaLabel: "Thumbs up, great!",
		cancelButtonText: `<i class="fa fa-thumbs-down"></i>`,
		cancelButtonAriaLabel: "Thumbs down",
		customClass: {
            confirmButton: "btn btn-primary",
            cancelButton: "btn btn-light",
        },
	});
}
document.querySelector(".btn-sweet-dialog").onclick = function () {	
	Swal.fire({
		title: "Do you want to save the changes?",
		showDenyButton: true,
		showCancelButton: true,
		confirmButtonText: "Save",
		denyButtonText: `Don't save`,
		customClass: {
            confirmButton: "btn btn-primary",
            cancelButton: "btn btn-danger",
            denyButton: "btn btn-dark",
		},
	}).then((result) => {
	if (result.isConfirmed) {
		Swal.fire({
			title: "Saved!",
			icon: "success",
			confirmButtonText: "Ok, got it!",
			customClass: {
				confirmButton: "btn btn-primary"
			}
		});
		} else if (result.isDenied) {
			Swal.fire({
				title: "Changes are not saved",
				icon: "info",
				confirmButtonText: "Ok, got it!",
				customClass: {
					confirmButton: "btn btn-primary"
				}
			});
		}
	});
}
document.querySelector(".btn-sweet-position").onclick = function () {	
	Swal.fire({
		position: "top-end",
		icon: "success",
		title: "Your work has been saved",
		showConfirmButton: false,
		timer: 1500
	});
}
document.querySelector(".btn-sweet-timer").onclick = function () {	
	let timerInterval;
	Swal.fire({
		title: "Auto close alert!",
		html: "I will close in <b></b> milliseconds.",
		timer: 2000,
		timerProgressBar: true,
		didOpen: () => {
			Swal.showLoading();
			const timer = Swal.getPopup().querySelector("b");
			timerInterval = setInterval(() => {
			  timer.textContent = `${Swal.getTimerLeft()}`;
			}, 100);
		},
		willClose: () => {
			clearInterval(timerInterval);
		}
	}).then((result) => {
		if (result.dismiss === Swal.DismissReason.timer) {
			console.log("I was closed by the timer");
		}
	});
}
document.querySelector(".btn-sweet-ajax").onclick = function () {	
	Swal.fire({
		title: "Submit your Github username",
		input: "text",
		inputAttributes: {
			autocapitalize: "off"
		},
		showCancelButton: true,
		confirmButtonText: "Look up",
		showLoaderOnConfirm: true,
		customClass: {
            confirmButton: "btn btn-primary",
			cancelButton: 'btn btn-light'
        },
		preConfirm: async (login) => {
			try {
				const githubUrl = `https://api.github.com/users/${login}`;
				const response = await fetch(githubUrl);
				if (!response.ok) {
					return Swal.showValidationMessage(`
						${JSON.stringify(await response.json())}
					`);
				}
				return response.json();
			} catch (error) {
				Swal.showValidationMessage(`Request failed: ${error}`);
			}
		},
		allowOutsideClick: () => !Swal.isLoading()
	}).then((result) => {
		if (result.isConfirmed) {
			Swal.fire({
				title: `${result.value.login}'s avatar`,
				imageUrl: result.value.avatar_url,
				confirmButtonText: "Ok, got it!",
				customClass: {
					confirmButton: "btn btn-primary"
				}
			});
		}
	});
}
document.querySelector(".btn-sweet-rtl").onclick = function () {
	Swal.fire({
		title: "هل تريد الاستمرار؟",
		icon: "question",
		iconHtml: "؟",
		confirmButtonText: "نعم",
		cancelButtonText: "لا",
		showCancelButton: true,
		showCloseButton: true,
		customClass: {
            confirmButton: "btn btn-primary",
			cancelButton: 'btn btn-danger'
        },
	});
}
document.querySelector(".btn-sweet-backdrop").onclick = function () {
	Swal.fire({
		title: "Custom width, padding, color, background.",
		width: 500,
		padding: "3em",
		color: "#fff",
		background: "#fff url(assets/images/swal2-backdrop.jpg)",
		backdrop: `rgba(var(--bs-dark-rgb), 0.5)`,
		confirmButtonText: "Ok, got it!",
		customClass: {
            confirmButton: "btn btn-primary",
		},
	});
}

document.querySelector(".btn-sweet-mixin").onclick = function () {	
	const Toast = Swal.mixin({
		toast: true,
		position: "top-end",
		showConfirmButton: false,
		timer: 300000,
		timerProgressBar: true,
		didOpen: (toast) => {
			toast.onmouseenter = Swal.stopTimer;
			toast.onmouseleave = Swal.resumeTimer;
		}
	});
	Toast.fire({
		icon: "success",
		title: "Signed in successfully"
	});	
}
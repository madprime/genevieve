$(function () {
  $('#report-filter-contradicted').change(function () {
    if (this.checked) {
      $('.flag-contradicted').addClass('hidden')
    } else {
      $('.flag-contradicted').removeClass('hidden')
    }
  })
})

var add_gennotes_data = function (data, textStatus, jqXHR) {
  for (var i = 0; i < data['results'].length; i++) {
    var result = data['results'][i]
    var rowGV = $('tr#gv-' + result['b37_id'])
    var elemGV = rowGV.find('td.gv-info-cell').empty()
    var variantDataTemplateHTML = $('#variant-data-template').html()
    var templateVariantData = _.template(variantDataTemplateHTML)
    for (var j = 0; j < result['relation_set'].length; j++) {
      var templated = templateVariantData({
        clinvarRCVAAccession: result['relation_set'][j]['tags']['clinvar-rcva:accession'],
        clinvarRCVADiseaseName: result['relation_set'][j]['tags']['clinvar-rcva:disease-name'],
        clinvarRCVASignificance: result['relation_set'][j]['tags']['clinvar-rcva:significance']
      })
      elemGV.append(templated)
      console.log(variantDataTemplateHTML)
      console.log(templated)
    }
    // No RCVA matches, prob variant was a multi-allele record - ignore it.
    if (result['relation_set'].length === 0) {
      rowGV.addClass('hidden')
    }
  }
}

$(function () {
  var variantList = $('tr.gv-row').map(function () {
    return $(this).attr('id').substring(3)
  }).toArray()
  console.log(variantList)
  var variantListJSON = JSON.stringify(
    variantList.map(function (v) {
        return 'b37-' + v
      })
    )
  console.log(variantListJSON)
  $.ajax(
    {
      url: 'http://gennotes.herokuapp.com/api/variant/',
      dataType: 'json',
      data: {'variant_list': variantListJSON, 'page_size': 100},
      success: add_gennotes_data
    }
  )
})

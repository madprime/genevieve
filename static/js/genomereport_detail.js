var add_id_data = function (b37ID, clinvarRelationsData, template, elem) {
  var varNameString = ''
  var varNames = []
  clinvarRelationsData.forEach(function (clinvarData) {
    var prefName = clinvarData['clinvar-rcva:preferred-name']
    if (!prefName) return

    if (varNameString) {
      // If this name already listed, don't output again.
      if (_.contains(varNames, prefName)) return
      varNameString = varNameString + '<br><small>or</small><br><b>' +
                      prefName + '</b>'
    } else {
      varNameString = '<b>' + clinvarData['clinvar-rcva:preferred-name']
    }
    varNames.push(prefName)
  })
  // console.log(varNames)
  var templated = template({
    clinvarRCVAPreferredName: varNameString,
    b37VariantID: b37ID
  })
  elem.append(templated)
  // console.log(elem)
}

var add_freq_data = function (clinvarRelationsData, template, elem) {
  var frequencies = []
  clinvarRelationsData.forEach(function (clinvarData) {
    if ('clinvar-rcva:esp-allele-frequency' in clinvarData) {
      var freq = clinvarData['clinvar-rcva:esp-allele-frequency']
      if (_.contains(frequencies, freq)) return
      frequencies.push(freq)
    }
  })
  // console.log(frequencies)
  var templated
  if (frequencies.length === 0) {
    templated = template({clinvarRCVAfreqESP: 'Unknown'})
  } else {
    templated = template({clinvarRCVAfreqESP: frequencies[0]})
  }
  elem.append(templated)
  // console.log(elem)
}

var add_info_data = function (clinvarRelationsData, template, elem) {
  clinvarRelationsData.forEach(
    function (clinvarData) {
      var templated = template({
        clinvarRCVAAccession: clinvarData['clinvar-rcva:accession'],
        clinvarRCVADiseaseName: clinvarData['clinvar-rcva:disease-name'],
        clinvarRCVASignificance: clinvarData['clinvar-rcva:significance']
      })
      // console.log(templated)
      elem.append(templated)
    }
  )
  // console.log(elem)
}

var add_gennotes_data = function (data, textStatus, jqXHR) {
  for (var i = 0; i < data['results'].length; i++) {
    var result = data['results'][i]
    // console.log(result['b37_id'])

    // Set up target elements by emptying them.
    var rowGV = $('tr#gv-' + result['b37_id'])
    var elemGVID = rowGV.find('td.gv-id-cell').empty()
    var elemGVFreq = rowGV.find('td.gv-freq-cell').empty()
    var elemGVInfo = rowGV.find('td.gv-info-cell').empty()

    // Load appropriate templates.
    var templateVariantID = _.template($('#variant-id-template').html())
    var templateVariantFreq = _.template($('#variant-freq-template').html())
    var templateVariantInfo = _.template($('#variant-info-template').html())

    // Extract list of Relations of type 'clinvar-rcva'.
    var clinvarRelationsData = []
    result['relation_set'].forEach(function (relation) {
      if (relation['tags']['type'] === 'clinvar-rcva') {
        clinvarRelationsData.push(relation['tags'])
      }
    })

    // No RCVA matches, prob variant was a multi-allele record - ignore it.
    if (clinvarRelationsData.length === 0) {
      rowGV.addClass('hidden')
      continue
    }

    // console.log('Adding ClinVar data')
    add_id_data(result['b37_id'], clinvarRelationsData, templateVariantID, elemGVID)
    add_freq_data(clinvarRelationsData, templateVariantFreq, elemGVFreq)
    add_info_data(clinvarRelationsData, templateVariantInfo, elemGVInfo)
  }
}

$(function () {
  var variantList = $('tr.gv-row').map(function () {
    return $(this).attr('id').substring(3)
  }).toArray()
  // console.log(variantList)
  var variantListJSON = JSON.stringify(
    variantList.map(function (v) {
        return 'b37-' + v
      })
    )
  // console.log(variantListJSON)
  $.ajax(
    {
      url: 'http://gennotes.herokuapp.com/api/variant/',
      dataType: 'json',
      data: {'variant_list': variantListJSON, 'page_size': 100},
      success: add_gennotes_data
    }
  )
})
